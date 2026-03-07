"""Gmail API service layer for MailFlow.

Handles OAuth 2.0 authentication and all interactions with the Gmail API.
"""
import base64
import email as email_lib
import os
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import config


def _get_credentials():
    """Load or refresh OAuth 2.0 credentials."""
    creds = None

    if os.path.exists(config.GOOGLE_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(
            config.GOOGLE_TOKEN_FILE, config.GMAIL_SCOPES
        )

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(config.GOOGLE_CREDENTIALS_FILE):
                raise FileNotFoundError(
                    f"credentials.json not found at {config.GOOGLE_CREDENTIALS_FILE}. "
                    "Please download it from the Google Cloud Console."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                config.GOOGLE_CREDENTIALS_FILE, config.GMAIL_SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(config.GOOGLE_TOKEN_FILE, "w") as token_file:
            token_file.write(creds.to_json())

    return creds


def get_gmail_service():
    """Return an authenticated Gmail API service object."""
    creds = _get_credentials()
    return build("gmail", "v1", credentials=creds)


def get_auth_url():
    """Return the OAuth 2.0 authorisation URL for web-based flow.

    Returns (auth_url, state) tuple.
    """
    if not os.path.exists(config.GOOGLE_CREDENTIALS_FILE):
        raise FileNotFoundError(
            f"credentials.json not found at {config.GOOGLE_CREDENTIALS_FILE}."
        )
    flow = InstalledAppFlow.from_client_secrets_file(
        config.GOOGLE_CREDENTIALS_FILE,
        config.GMAIL_SCOPES,
        redirect_uri="http://localhost:5000/auth/callback",
    )
    auth_url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true", prompt="consent"
    )
    return auth_url, state


def exchange_code(code, state):
    """Exchange the authorisation code for credentials and persist them."""
    flow = InstalledAppFlow.from_client_secrets_file(
        config.GOOGLE_CREDENTIALS_FILE,
        config.GMAIL_SCOPES,
        redirect_uri="http://localhost:5000/auth/callback",
    )
    flow.fetch_token(code=code)
    creds = flow.credentials
    with open(config.GOOGLE_TOKEN_FILE, "w") as token_file:
        token_file.write(creds.to_json())
    return creds


def is_authenticated():
    """Return True if valid credentials exist."""
    if not os.path.exists(config.GOOGLE_TOKEN_FILE):
        return False
    try:
        creds = Credentials.from_authorized_user_file(
            config.GOOGLE_TOKEN_FILE, config.GMAIL_SCOPES
        )
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(config.GOOGLE_TOKEN_FILE, "w") as token_file:
                token_file.write(creds.to_json())
        return creds is not None and creds.valid
    except Exception:
        return False


def revoke_token():
    """Remove the stored token, effectively logging out."""
    if os.path.exists(config.GOOGLE_TOKEN_FILE):
        os.remove(config.GOOGLE_TOKEN_FILE)


# ---------------------------------------------------------------------------
# Email helpers
# ---------------------------------------------------------------------------

def _decode_body(payload):
    """Recursively extract plain-text body from a Gmail message payload."""
    body = ""
    if payload.get("mimeType") == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            body = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
    elif payload.get("mimeType") == "text/html" and not body:
        data = payload.get("body", {}).get("data", "")
        if data:
            # Very simple HTML → plain-text strip
            html = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
            import re
            body = re.sub(r"<[^>]+>", " ", html)
    for part in payload.get("parts", []):
        child_body = _decode_body(part)
        if child_body:
            body = child_body
            break
    return body


def _parse_message(msg):
    """Convert a raw Gmail API message dict into a clean dict."""
    headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
    date_str = headers.get("Date", "")
    try:
        date = email_lib.utils.parsedate_to_datetime(date_str)
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
    except Exception:
        date = datetime.now(timezone.utc)

    body = _decode_body(msg["payload"])

    return {
        "gmail_id": msg["id"],
        "thread_id": msg.get("threadId", ""),
        "subject": headers.get("Subject", "(no subject)"),
        "sender": headers.get("From", ""),
        "recipient": headers.get("To", ""),
        "snippet": msg.get("snippet", ""),
        "body": body,
        "date": date,
        "is_read": "UNREAD" not in msg.get("labelIds", []),
    }


def list_emails(max_results=None):
    """Fetch and parse up to *max_results* emails from the inbox."""
    max_results = max_results or config.EMAIL_FETCH_LIMIT
    service = get_gmail_service()
    result = (
        service.users()
        .messages()
        .list(userId="me", maxResults=max_results, labelIds=["INBOX"])
        .execute()
    )
    messages = result.get("messages", [])
    emails = []
    for m in messages:
        try:
            msg = (
                service.users()
                .messages()
                .get(userId="me", id=m["id"], format="full")
                .execute()
            )
            emails.append(_parse_message(msg))
        except HttpError:
            continue
    return emails


def get_email(gmail_id):
    """Fetch a single email by its Gmail message ID."""
    service = get_gmail_service()
    msg = (
        service.users()
        .messages()
        .get(userId="me", id=gmail_id, format="full")
        .execute()
    )
    return _parse_message(msg)


def send_reply(to, subject, body, thread_id=None):
    """Send a reply email via the Gmail API.

    Parameters
    ----------
    to : str  – recipient address
    subject : str – reply subject
    body : str – plain-text reply body
    thread_id : str | None – Gmail thread ID to keep the reply in-thread
    """
    service = get_gmail_service()

    mime_msg = MIMEMultipart()
    mime_msg["to"] = to
    mime_msg["subject"] = subject
    mime_msg.attach(MIMEText(body, "plain"))

    raw = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode()
    body_payload = {"raw": raw}
    if thread_id:
        body_payload["threadId"] = thread_id

    result = (
        service.users()
        .messages()
        .send(userId="me", body=body_payload)
        .execute()
    )
    return result


def mark_as_read(gmail_id):
    """Remove the UNREAD label from a message."""
    service = get_gmail_service()
    service.users().messages().modify(
        userId="me",
        id=gmail_id,
        body={"removeLabelIds": ["UNREAD"]},
    ).execute()

"""Auto-reply engine for MailFlow.

Given an email and its assigned category, this module finds the best
reply template and optionally sends it via the Gmail API.
"""
from models import Email, ReplyTemplate, get_session
from gmail_service import send_reply


def get_template_for_category(category_id: int) -> ReplyTemplate | None:
    """Return the first reply template for the given category, or None."""
    session = get_session()
    try:
        return (
            session.query(ReplyTemplate)
            .filter_by(category_id=category_id)
            .first()
        )
    finally:
        session.close()


def build_reply_body(template: ReplyTemplate, email_data: dict) -> tuple[str, str]:
    """Render the template subject and body using simple placeholder substitution.

    Supported placeholders:
    - {sender}  – the sender's name/address
    - {subject} – the original email subject
    """
    subject = (template.subject_prefix or "Re: ") + email_data.get("subject", "")
    body = template.body
    body = body.replace("{sender}", email_data.get("sender", ""))
    body = body.replace("{subject}", email_data.get("subject", ""))
    return subject, body


def auto_reply(email_data: dict, category_id: int) -> dict:
    """Send an auto-reply if the category has a template with auto_reply=True.

    Returns a status dict: {"sent": bool, "message": str}
    """
    session = get_session()
    try:
        template = (
            session.query(ReplyTemplate)
            .filter_by(category_id=category_id, auto_reply=True)
            .first()
        )
        if template is None:
            return {"sent": False, "message": "No auto-reply template for category."}

        subject, body = build_reply_body(template, email_data)
        result = send_reply(
            to=email_data.get("sender", ""),
            subject=subject,
            body=body,
            thread_id=email_data.get("thread_id"),
        )
        # Mark email as replied in DB
        email_record = (
            session.query(Email)
            .filter_by(gmail_id=email_data.get("gmail_id", ""))
            .first()
        )
        if email_record:
            email_record.is_replied = True
            session.commit()

        return {"sent": True, "message": "Reply sent.", "gmail_result": result}
    except Exception as exc:
        return {"sent": False, "message": str(exc)}
    finally:
        session.close()


def send_manual_reply(
    email_data: dict, template_id: int
) -> dict:
    """Send a reply using the template specified by *template_id*.

    Returns a status dict: {"sent": bool, "message": str}
    """
    session = get_session()
    try:
        template = session.query(ReplyTemplate).filter_by(id=template_id).first()
        if template is None:
            return {"sent": False, "message": f"Template {template_id} not found."}

        subject, body = build_reply_body(template, email_data)
        result = send_reply(
            to=email_data.get("sender", ""),
            subject=subject,
            body=body,
            thread_id=email_data.get("thread_id"),
        )
        # Mark email as replied in DB
        email_record = (
            session.query(Email)
            .filter_by(gmail_id=email_data.get("gmail_id", ""))
            .first()
        )
        if email_record:
            email_record.is_replied = True
            session.commit()

        return {"sent": True, "message": "Reply sent.", "gmail_result": result}
    except Exception as exc:
        return {"sent": False, "message": str(exc)}
    finally:
        session.close()

import os
import base64
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

creds = None

if os.path.exists('token.json'):
    creds = Credentials.from_authorized_user_file('token.json', SCOPES)

if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(
            'credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)

    with open('token.json', 'w') as token:
        token.write(creds.to_json())

service = build('gmail', 'v1', credentials=creds)

# Call the Gmail API to fetch INBOX
results = service.users().messages().list(userId='me', labelIds=['INBOX'], maxResults=1).execute()
messages = results.get('messages', [])
if not messages:
    print('No messages found.')
else:
    for message in messages:
        #get the message's headers
        msg = service.users().messages().get(userId='me', id=message['id']).execute()
        headers = msg['payload']['headers']
        for header in headers:
            if header['name'] == 'Subject':
                print('Subject: ' + header['value'])
            if header['name'] == 'From':
                print('From: ' + header['value'])
            if header['name'] == 'Date':
                print('Date: ' + header['value'])
            if header['name'] == 'To':
                print('To: ' + header['value'])
msg = service.users().messages().get(
    userId='me',
    id=message['id'],
    format='full'
).execute()

headers = msg['payload']['headers']

for header in headers:
    if header['name'] == 'Subject':
        print('Subject:', header['value'])

payload = msg['payload']

body_data = None
if 'parts' in payload:
    for part in payload['parts']:
        if part['mimeType'] == 'text/plain':
            body_data = part['body'].get('data')
            break
else:
    body_data = payload['body'].get('data')

if body_data:
    decoded_body = base64.urlsafe_b64decode(body_data).decode('utf-8')
    print(decoded_body)
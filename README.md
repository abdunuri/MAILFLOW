# MailFlow

MailFlow is a Gmail management assistant with a Flask backend and a browser-based dashboard for syncing, categorizing, and replying to emails.

## Main Concept

The project turns a Gmail inbox into a rule-driven workflow tool. Users connect Gmail through OAuth, sync recent emails, define categories with keyword rules, attach reply templates, and optionally use Gemini to categorize or generate replies.

## Core Features

- Gmail OAuth login and logout
- Inbox sync through the Gmail API
- Email caching with SQLAlchemy models
- Category rules for sender, subject, and body keywords
- Priority-based category matching
- Reply templates with `{sender}` and `{subject}` placeholders
- Manual replies from the UI
- Optional AI-generated replies with Gemini
- Dashboard statistics and category breakdown
- Pytest coverage for API, models, and categorization logic

## Tech Stack

- Python and Flask
- SQLAlchemy with SQLite by default
- Gmail API
- Google Gemini API integration
- Vanilla JavaScript frontend
- Tailwind CDN styling
- pytest

## Run Locally

1. Create a Gmail OAuth client in Google Cloud.
2. Save the downloaded credentials as `backend/credentials.json`.
3. Install dependencies:

```bash
cd backend
pip install -r requirements.txt
```

4. Optional `.env`:

```env
SECRET_KEY=your-secret
DATABASE_URL=sqlite:///mailflow.db
GEMINI_API_KEY=your_gemini_key
EMAIL_FETCH_LIMIT=50
```

5. Start the app:

```bash
python app.py
```

Open `http://localhost:5000`.

## Tests

```bash
python -m pytest tests -v
```

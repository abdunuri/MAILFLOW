# MailFlow – Smart Email Management Assistant

> A SaaS-like Python bot that reads, categorises, and auto-replies to Gmail messages based on user-defined rules.

---

## Features

| Feature | Description |
|---|---|
| 📥 **Gmail Inbox Sync** | Fetches emails via the Gmail API (OAuth 2.0) |
| 🏷️ **Smart Categorisation** | Rule-based engine (sender / subject / body keywords) with optional AI fallback via Google Gemini |
| 🤖 **Auto-Reply** | Pre-specified reply templates or AI-generated replies when a matching email arrives |
| ↩️ **Manual Reply** | Send a reply from a template, generate with AI, or write a custom message directly in the UI |
| 📊 **Dashboard** | Stats overview and per-category email counts |
| 🌙 **Dark Mode** | Persisted light/dark theme toggle |

---

## Project Structure

```
MAILFLOW/
├── backend/
│   ├── app.py              ← Flask REST API (entry point)
│   ├── gmail_service.py    ← Gmail API integration & OAuth helpers
│   ├── categorizer.py      ← Email categorisation engine
│   ├── ai_service.py       ← Google Gemini AI (categorisation & reply generation)
│   ├── replier.py          ← Auto-reply & manual reply logic
│   ├── models.py           ← SQLAlchemy ORM models (SQLite by default)
│   ├── config.py           ← Environment-based configuration
│   └── requirements.txt
├── frontend/
│   ├── index.html          ← Single-page application shell
│   ├── app.js              ← Vanilla JS application logic
│   └── styles.css          ← Tailwind CSS utility overrides
├── tests/
│   ├── test_categorizer.py
│   ├── test_models.py
│   └── test_api.py
├── credentials.json.example
└── README.md
```

---

## Quick Start

### 1. Google Cloud Setup

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (or reuse an existing one).
3. Enable the **Gmail API** under *APIs & Services → Library*.
4. Go to *APIs & Services → Credentials* → **Create Credentials → OAuth client ID**.
   - Application type: **Desktop app** (for local development).
5. Download the JSON file and save it as `backend/credentials.json`.

### 2. Environment Variables (optional)

Create `backend/.env` and adjust as needed:

```dotenv
SECRET_KEY=your-secret-key
DEBUG=true
DATABASE_URL=sqlite:///mailflow.db
GEMINI_API_KEY=...      # optional – enables AI categorisation & AI-generated replies
EMAIL_FETCH_LIMIT=50
```

### 3. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 4. Run the App

```bash
cd backend
python app.py
```

Then open **http://localhost:5000** in your browser.

On first run, click **Connect Gmail** to complete the OAuth flow.  
The token is saved locally in `backend/token.json` for future runs.

---

## Usage Guide

### Categories

Go to the **Categories** page and click **+ New Category**.

Fill in one or more of:
- **Sender keywords** – match the `From:` header (e.g. `@github.com, noreply`)
- **Subject keywords** – match the email subject (e.g. `invoice, receipt`)
- **Body keywords** – match the email body (e.g. `unsubscribe, confidential`)

Rules are AND-combined per category (all non-empty fields must match).  
Use **Priority** to control which rule wins when multiple categories apply.

### Reply Templates

Go to **Reply Templates** → **+ New Template**.

- Assign a template to a category.
- Use `{sender}` and `{subject}` as placeholders in the body.
- Enable **Auto-reply** to send the template automatically when a matching email is synced.

### Sync

Click **Sync Inbox** in the sidebar to pull new emails, categorise them, and trigger any auto-replies.

---

## Running Tests

```bash
pip install pytest
python -m pytest tests/ -v
```

---

## Technology Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12 + Flask 3 |
| Database | SQLite (via SQLAlchemy 2) |
| Gmail | Google API Python Client |
| AI (optional) | OpenAI GPT-3.5 |
| Frontend | Vanilla JS + Tailwind CSS (CDN) |
| Tests | pytest |

"""Email categorisation engine for MailFlow.

Rules are stored in the database.  Each Category has comma-separated keyword
lists for sender, subject, and body matching.  The engine returns the
highest-priority category whose rules match the email.

Optionally, if an OpenAI API key is configured, an AI-based fallback can
assign a category from the list when no rule matches.
"""
import re

import config


def _keywords(raw: str) -> list[str]:
    """Split a comma-separated keyword string into a cleaned list."""
    return [k.strip().lower() for k in raw.split(",") if k.strip()]


def _matches_keywords(text: str, keywords: list[str]) -> bool:
    """Return True if *any* keyword is found (case-insensitive) in *text*."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)


def categorize_email(email_data: dict, categories: list) -> object | None:
    """Return the best-matching Category ORM object, or None.

    Parameters
    ----------
    email_data : dict  with keys: sender, subject, body
    categories : list of Category ORM objects (sorted by priority descending)
    """
    if not categories:
        return None

    # Sort by priority (descending) so higher-priority rules win
    sorted_cats = sorted(categories, key=lambda c: c.priority, reverse=True)

    for cat in sorted_cats:
        sender_kws = _keywords(cat.sender_keywords or "")
        subject_kws = _keywords(cat.subject_keywords or "")
        body_kws = _keywords(cat.body_keywords or "")

        sender_match = (not sender_kws) or _matches_keywords(
            email_data.get("sender", ""), sender_kws
        )
        subject_match = (not subject_kws) or _matches_keywords(
            email_data.get("subject", ""), subject_kws
        )
        body_match = (not body_kws) or _matches_keywords(
            email_data.get("body", "") or email_data.get("snippet", ""), body_kws
        )

        if sender_match and subject_match and body_match:
            return cat

    # AI-powered fallback (requires OPENAI_API_KEY)
    if config.OPENAI_API_KEY:
        return _ai_categorize(email_data, sorted_cats)

    return None


def _ai_categorize(email_data: dict, categories: list) -> object | None:
    """Use OpenAI to assign one of the existing categories to an email."""
    try:
        from openai import OpenAI

        client = OpenAI(api_key=config.OPENAI_API_KEY)
        category_names = [c.name for c in categories]
        prompt = (
            "You are an email categorisation assistant.\n"
            f"Available categories: {', '.join(category_names)}\n"
            f"Email subject: {email_data.get('subject', '')}\n"
            f"Email sender: {email_data.get('sender', '')}\n"
            f"Email snippet: {email_data.get('snippet', '')[:300]}\n\n"
            "Respond with ONLY the category name that best fits this email, "
            "or 'None' if none apply."
        )
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=20,
            temperature=0,
        )
        chosen = response.choices[0].message.content.strip()
        for cat in categories:
            if cat.name.lower() == chosen.lower():
                return cat
    except Exception:
        pass
    return None


def apply_categories_to_emails(emails: list, categories: list) -> list:
    """Return *emails* list with 'matched_category' key added to each item.

    Parameters
    ----------
    emails : list of dicts (as returned by gmail_service.list_emails)
    categories : list of Category ORM objects
    """
    result = []
    for email_data in emails:
        cat = categorize_email(email_data, categories)
        email_data["matched_category"] = cat
        result.append(email_data)
    return result

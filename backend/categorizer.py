"""Email categorisation engine for MailFlow.

Rules are stored in the database.  Each Category has comma-separated keyword
lists for sender, subject, and body matching.  The engine returns the
highest-priority category whose rules match the email.

Optionally, if a Gemini API key is configured, an AI-based fallback can
assign a category from the list when no rule matches.
"""
from ai_service import ai_categorize as _ai_categorize


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

    # AI-powered fallback (requires GEMINI_API_KEY)
    category_names = [c.name for c in sorted_cats]
    chosen = _ai_categorize(email_data, category_names)
    if isinstance(chosen, str) and chosen:
        for cat in sorted_cats:
            if cat.name.lower() == chosen.lower():
                return cat
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

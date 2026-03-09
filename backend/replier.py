"""Auto-reply engine for MailFlow.

Given an email and its assigned category, this module finds the best
reply template and optionally sends it via the Gmail API.
"""
import config
from models import Category, Email, ReplyTemplate, get_session
from gmail_service import send_reply


def _has_gemini_key() -> bool:
    """Return True if GEMINI_API_KEY is set (enables AI reply fallback when no template)."""
    return bool(config.GEMINI_API_KEY)


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


def auto_reply(email_data: dict, category_id: int, session=None) -> dict:
    """Send an auto-reply if the category has a template with auto_reply=True,
    or if the category has use_ai_reply=True (AI generates the reply).

    When session is provided (e.g. from sync), the email must already be committed
    so _mark_email_replied can find it.

    Returns a status dict: {"sent": bool, "message": str}
    """
    sess = session or get_session()
    should_close = session is None
    try:
        category = sess.query(Category).filter_by(id=category_id).first()
        if not category:
            return {"sent": False, "message": "Category not found."}

        use_ai = getattr(category, "use_ai_reply", False)

        # 1. Prefer template with auto_reply if it exists
        template = (
            sess.query(ReplyTemplate)
            .filter_by(category_id=category_id, auto_reply=True)
            .first()
        )
        if template is not None:
            subject, body = build_reply_body(template, email_data)
            result = send_reply(
                to=email_data.get("sender", ""),
                subject=subject,
                body=body,
                thread_id=email_data.get("thread_id"),
            )
            _mark_email_replied(sess, email_data.get("gmail_id", ""))
            return {"sent": True, "message": "Reply sent.", "gmail_result": result}

        # 2. No template: try AI if use_ai_reply OR GEMINI_API_KEY is set (fallback)
        if use_ai or _has_gemini_key():
            from ai_service import ai_generate_reply
            ai_result = ai_generate_reply(email_data, category.name)
            if ai_result[0] is not None:
                subject, body = ai_result
                result = send_reply(
                    to=email_data.get("sender", ""),
                    subject=subject,
                    body=body,
                    thread_id=email_data.get("thread_id"),
                )
                _mark_email_replied(sess, email_data.get("gmail_id", ""))
                return {"sent": True, "message": "AI reply sent.", "gmail_result": result}
            return {"sent": False, "message": ai_result[1] or "AI reply failed."}

        return {"sent": False, "message": "No auto-reply template. Add GEMINI_API_KEY to .env or add a template."}
    except Exception as exc:
        return {"sent": False, "message": str(exc)}
    finally:
        if should_close:
            sess.close()


def _mark_email_replied(session, gmail_id: str) -> None:
    """Mark an email as replied in the database."""
    email_record = session.query(Email).filter_by(gmail_id=gmail_id).first()
    if email_record:
        email_record.is_replied = True
        session.commit()


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
        _mark_email_replied(session, email_data.get("gmail_id", ""))

        return {"sent": True, "message": "Reply sent.", "gmail_result": result}
    except Exception as exc:
        return {"sent": False, "message": str(exc)}
    finally:
        session.close()

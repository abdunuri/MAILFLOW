"""MailFlow – Flask REST API entry point.

Run with:
    cd backend
    python app.py
"""
import sys
import os

# Ensure the backend directory is on sys.path when running directly
sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

import config
from models import Category, Email, ReplyTemplate, get_session, init_db
from categorizer import categorize_email
from replier import auto_reply, send_manual_reply

app = Flask(
    __name__,
    static_folder=os.path.join(os.path.dirname(__file__), "..", "frontend"),
    static_url_path="",
)
app.secret_key = config.SECRET_KEY
CORS(app)

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

@app.before_request
def _ensure_db():
    init_db()


# ---------------------------------------------------------------------------
# Serve frontend
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@app.route("/auth/status")
def auth_status():
    from gmail_service import is_authenticated
    return jsonify({"authenticated": is_authenticated()})


@app.route("/auth/login")
def auth_login():
    from gmail_service import get_auth_url
    try:
        auth_url, _ = get_auth_url()
        return jsonify({"auth_url": auth_url})
    except FileNotFoundError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/auth/callback")
def auth_callback():
    from gmail_service import exchange_code
    code = request.args.get("code")
    state = request.args.get("state", "")
    if not code:
        return jsonify({"error": "No code provided."}), 400
    try:
        exchange_code(code, state)
        return send_from_directory(app.static_folder, "index.html")
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/auth/logout", methods=["POST"])
def auth_logout():
    from gmail_service import revoke_token
    revoke_token()
    return jsonify({"message": "Logged out."})


# ---------------------------------------------------------------------------
# Email endpoints
# ---------------------------------------------------------------------------

@app.route("/api/emails")
def get_emails():
    """Return cached emails (with optional Gmail sync)."""
    sync = request.args.get("sync", "false").lower() == "true"
    session = get_session()
    try:
        if sync:
            _sync_emails(session)
        emails = session.query(Email).order_by(Email.date.desc()).all()
        return jsonify([e.to_dict() for e in emails])
    finally:
        session.close()


@app.route("/api/emails/<gmail_id>")
def get_email(gmail_id):
    session = get_session()
    try:
        email = session.query(Email).filter_by(gmail_id=gmail_id).first()
        if not email:
            # Try to fetch from Gmail directly
            from gmail_service import get_email as gmail_get
            try:
                email_data = gmail_get(gmail_id)
                return jsonify(email_data)
            except Exception as exc:
                return jsonify({"error": str(exc)}), 404
        return jsonify(email.to_dict())
    finally:
        session.close()


@app.route("/api/emails/sync", methods=["POST"])
def sync_emails():
    """Pull latest emails from Gmail, categorise, and cache them."""
    from gmail_service import is_authenticated
    if not is_authenticated():
        return jsonify({"error": "Not authenticated. Please connect your Gmail account."}), 401
    session = get_session()
    try:
        result = _sync_emails(session)
        synced = result["synced"]
        msg = f"Synced {synced} emails."
        if result.get("replies_sent"):
            msg += f" {result['replies_sent']} auto-replies sent."
        if result.get("reply_errors"):
            msg += f" Errors: {'; '.join(result['reply_errors'][:3])}"
        return jsonify({"synced": synced, "message": msg, **result})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        session.close()


@app.route("/api/emails/<gmail_id>/generate-reply", methods=["POST"])
def generate_ai_reply(gmail_id):
    """Generate an AI reply for an email. Returns subject and body."""
    session = get_session()
    try:
        email = session.query(Email).filter_by(gmail_id=gmail_id).first()
        if not email:
            return jsonify({"error": "Email not found."}), 404
        category_name = email.category.name if email.category else "General"
        from ai_service import ai_generate_reply
        result = ai_generate_reply(email.to_dict(), category_name)
        if result[0] is None:
            return jsonify({"error": result[1] or "AI reply generation failed."}), 503
        subject, body = result
        return jsonify({"subject": subject, "body": body})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        session.close()


@app.route("/api/emails/<gmail_id>/categorize", methods=["POST"])
def categorize_single(gmail_id):
    """Re-run categorisation on a single email."""
    session = get_session()
    try:
        email = session.query(Email).filter_by(gmail_id=gmail_id).first()
        if not email:
            return jsonify({"error": "Email not found."}), 404
        categories = session.query(Category).all()
        cat = categorize_email(email.to_dict(), categories)
        if cat:
            email.category_id = cat.id
            session.commit()
        return jsonify(email.to_dict())
    finally:
        session.close()


@app.route("/api/emails/<gmail_id>/reply", methods=["POST"])
def reply_to_email(gmail_id):
    """Send a reply using a template or manual body."""
    data = request.get_json() or {}
    session = get_session()
    try:
        email = session.query(Email).filter_by(gmail_id=gmail_id).first()
        if not email:
            return jsonify({"error": "Email not found."}), 404

        template_id = data.get("template_id")
        if template_id:
            result = send_manual_reply(email.to_dict(), int(template_id))
        else:
            # Ad-hoc reply body provided directly
            body = data.get("body", "")
            subject = data.get("subject", f"Re: {email.subject}")
            if not body:
                return jsonify({"error": "Provide 'template_id' or 'body'."}), 400
            from gmail_service import send_reply
            gm_result = send_reply(
                to=email.sender,
                subject=subject,
                body=body,
                thread_id=email.thread_id,
            )
            email.is_replied = True
            session.commit()
            result = {"sent": True, "message": "Reply sent.", "gmail_result": gm_result}

        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Category endpoints
# ---------------------------------------------------------------------------

@app.route("/api/categories", methods=["GET"])
def list_categories():
    session = get_session()
    try:
        cats = session.query(Category).order_by(Category.priority.desc()).all()
        return jsonify([c.to_dict() for c in cats])
    finally:
        session.close()


@app.route("/api/categories", methods=["POST"])
def create_category():
    data = request.get_json()
    if not data or not data.get("name"):
        return jsonify({"error": "Category 'name' is required."}), 400
    session = get_session()
    try:
        cat = Category(
            name=data["name"],
            description=data.get("description", ""),
            color=data.get("color", "#6366f1"),
            sender_keywords=data.get("sender_keywords", ""),
            subject_keywords=data.get("subject_keywords", ""),
            body_keywords=data.get("body_keywords", ""),
            priority=int(data.get("priority", 0)),
            use_ai_reply=bool(data.get("use_ai_reply", False)),
        )
        session.add(cat)
        session.commit()
        return jsonify(cat.to_dict()), 201
    except Exception as exc:
        session.rollback()
        return jsonify({"error": str(exc)}), 500
    finally:
        session.close()


@app.route("/api/categories/<int:cat_id>", methods=["PUT"])
def update_category(cat_id):
    data = request.get_json() or {}
    session = get_session()
    try:
        cat = session.query(Category).filter_by(id=cat_id).first()
        if not cat:
            return jsonify({"error": "Category not found."}), 404
        for field in ("name", "description", "color", "sender_keywords",
                      "subject_keywords", "body_keywords"):
            if field in data:
                setattr(cat, field, data[field])
        if "priority" in data:
            cat.priority = int(data["priority"])
        if "use_ai_reply" in data:
            cat.use_ai_reply = bool(data["use_ai_reply"])
        session.commit()
        return jsonify(cat.to_dict())
    except Exception as exc:
        session.rollback()
        return jsonify({"error": str(exc)}), 500
    finally:
        session.close()


@app.route("/api/categories/<int:cat_id>", methods=["DELETE"])
def delete_category(cat_id):
    session = get_session()
    try:
        cat = session.query(Category).filter_by(id=cat_id).first()
        if not cat:
            return jsonify({"error": "Category not found."}), 404
        session.delete(cat)
        session.commit()
        return jsonify({"message": "Deleted."})
    except Exception as exc:
        session.rollback()
        return jsonify({"error": str(exc)}), 500
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Reply template endpoints
# ---------------------------------------------------------------------------

@app.route("/api/templates", methods=["GET"])
def list_templates():
    session = get_session()
    try:
        category_id = request.args.get("category_id")
        q = session.query(ReplyTemplate)
        if category_id:
            q = q.filter_by(category_id=int(category_id))
        templates = q.all()
        return jsonify([t.to_dict() for t in templates])
    finally:
        session.close()


@app.route("/api/templates", methods=["POST"])
def create_template():
    data = request.get_json()
    if not data or not data.get("category_id") or not data.get("body"):
        return jsonify({"error": "'category_id' and 'body' are required."}), 400
    session = get_session()
    try:
        cat = session.query(Category).filter_by(id=int(data["category_id"])).first()
        if not cat:
            return jsonify({"error": "Category not found."}), 404
        tmpl = ReplyTemplate(
            category_id=int(data["category_id"]),
            name=data.get("name", "Template"),
            subject_prefix=data.get("subject_prefix", "Re: "),
            body=data["body"],
            auto_reply=bool(data.get("auto_reply", False)),
        )
        session.add(tmpl)
        session.commit()
        return jsonify(tmpl.to_dict()), 201
    except Exception as exc:
        session.rollback()
        return jsonify({"error": str(exc)}), 500
    finally:
        session.close()


@app.route("/api/templates/<int:tmpl_id>", methods=["PUT"])
def update_template(tmpl_id):
    data = request.get_json() or {}
    session = get_session()
    try:
        tmpl = session.query(ReplyTemplate).filter_by(id=tmpl_id).first()
        if not tmpl:
            return jsonify({"error": "Template not found."}), 404
        for field in ("name", "subject_prefix", "body"):
            if field in data:
                setattr(tmpl, field, data[field])
        if "auto_reply" in data:
            tmpl.auto_reply = bool(data["auto_reply"])
        if "category_id" in data:
            tmpl.category_id = int(data["category_id"])
        session.commit()
        return jsonify(tmpl.to_dict())
    except Exception as exc:
        session.rollback()
        return jsonify({"error": str(exc)}), 500
    finally:
        session.close()


@app.route("/api/templates/<int:tmpl_id>", methods=["DELETE"])
def delete_template(tmpl_id):
    session = get_session()
    try:
        tmpl = session.query(ReplyTemplate).filter_by(id=tmpl_id).first()
        if not tmpl:
            return jsonify({"error": "Template not found."}), 404
        session.delete(tmpl)
        session.commit()
        return jsonify({"message": "Deleted."})
    except Exception as exc:
        session.rollback()
        return jsonify({"error": str(exc)}), 500
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Dashboard stats endpoint
# ---------------------------------------------------------------------------

@app.route("/api/stats")
def stats():
    session = get_session()
    try:
        total = session.query(Email).count()
        unread = session.query(Email).filter_by(is_read=False).count()
        replied = session.query(Email).filter_by(is_replied=True).count()
        cats = session.query(Category).count()
        # Per-category counts
        cat_counts = []
        for cat in session.query(Category).all():
            count = session.query(Email).filter_by(category_id=cat.id).count()
            cat_counts.append({"name": cat.name, "color": cat.color, "count": count})
        return jsonify({
            "total_emails": total,
            "unread": unread,
            "replied": replied,
            "categories": cats,
            "by_category": cat_counts,
        })
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _sync_emails(session) -> dict:
    """Fetch emails from Gmail, cache them, and apply categorisation.
    Returns dict with synced count, replies_sent, and reply_errors.
    """
    from gmail_service import list_emails
    email_list = list_emails()
    categories = session.query(Category).all()
    synced = 0
    replies_sent = 0
    reply_errors = []
    for email_data in email_list:
        existing = (
            session.query(Email)
            .filter_by(gmail_id=email_data["gmail_id"])
            .first()
        )
        if existing:
            continue  # already cached
        cat = categorize_email(email_data, categories)
        email_record = Email(
            gmail_id=email_data["gmail_id"],
            thread_id=email_data.get("thread_id", ""),
            subject=email_data.get("subject", ""),
            sender=email_data.get("sender", ""),
            recipient=email_data.get("recipient", ""),
            snippet=email_data.get("snippet", ""),
            body=email_data.get("body", ""),
            date=email_data.get("date"),
            is_read=email_data.get("is_read", False),
            category_id=cat.id if cat else None,
        )
        session.add(email_record)
        session.commit()  # Commit so auto_reply can mark email as replied
        if cat:
            result = auto_reply(email_data, cat.id, session=session)
            if result.get("sent"):
                replies_sent += 1
            elif result.get("message"):
                reply_errors.append(f"{email_data.get('subject', '')[:30]}: {result['message']}")
        synced += 1
    return {"synced": synced, "replies_sent": replies_sent, "reply_errors": reply_errors}


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    init_db()
    app.run(debug=config.DEBUG, port=5000)

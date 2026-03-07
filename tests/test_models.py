"""Unit tests for the database models."""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

# Use an in-memory SQLite database for tests
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")


@pytest.fixture(autouse=True)
def fresh_db(monkeypatch, tmp_path):
    """Give each test its own in-memory database."""
    # Patch DATABASE_URL and reset module-level engine/session singletons
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    import importlib
    import config as cfg
    cfg.DATABASE_URL = "sqlite:///:memory:"

    import models
    importlib.reload(models)
    models.init_db()
    yield
    # cleanup
    models._engine = None
    models._Session = None


def test_category_create_and_to_dict():
    import models
    session = models.get_session()
    cat = models.Category(
        name="Work",
        description="Work emails",
        color="#ff0000",
        sender_keywords="@company.com",
        subject_keywords="project, meeting",
        priority=5,
    )
    session.add(cat)
    session.commit()

    fetched = session.query(models.Category).filter_by(name="Work").first()
    assert fetched is not None
    d = fetched.to_dict()
    assert d["name"] == "Work"
    assert d["color"] == "#ff0000"
    assert d["priority"] == 5
    assert d["sender_keywords"] == "@company.com"
    session.close()


def test_category_name_unique():
    import models
    from sqlalchemy.exc import IntegrityError
    session = models.get_session()
    session.add(models.Category(name="Dupe"))
    session.commit()
    session.add(models.Category(name="Dupe"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
    session.close()


def test_reply_template_create_and_relationship():
    import models
    session = models.get_session()
    cat = models.Category(name="Support", body_keywords="help, issue")
    session.add(cat)
    session.commit()

    tmpl = models.ReplyTemplate(
        category_id=cat.id,
        name="Ack template",
        subject_prefix="Re: ",
        body="Thank you for contacting support.",
        auto_reply=True,
    )
    session.add(tmpl)
    session.commit()

    fetched = session.query(models.ReplyTemplate).filter_by(name="Ack template").first()
    assert fetched is not None
    assert fetched.auto_reply is True
    assert fetched.category.name == "Support"
    d = fetched.to_dict()
    assert d["auto_reply"] is True
    assert d["category_id"] == cat.id
    session.close()


def test_email_create_and_category_relation():
    import models
    from datetime import datetime, timezone
    session = models.get_session()
    cat = models.Category(name="Newsletter")
    session.add(cat)
    session.commit()

    email = models.Email(
        gmail_id="abc123",
        thread_id="thread1",
        subject="Weekly digest",
        sender="news@example.com",
        snippet="Top stories this week…",
        date=datetime.now(timezone.utc),
        category_id=cat.id,
    )
    session.add(email)
    session.commit()

    fetched = session.query(models.Email).filter_by(gmail_id="abc123").first()
    assert fetched is not None
    d = fetched.to_dict()
    assert d["subject"] == "Weekly digest"
    assert d["category_name"] == "Newsletter"
    session.close()


def test_email_gmail_id_unique():
    import models
    from sqlalchemy.exc import IntegrityError
    session = models.get_session()
    session.add(models.Email(gmail_id="uid1", subject="First"))
    session.commit()
    session.add(models.Email(gmail_id="uid1", subject="Second"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
    session.close()


def test_cascade_delete_category_nullifies_email_category():
    """Deleting a category NULLs the email's category_id instead of deleting the email."""
    import models
    session = models.get_session()
    cat = models.Category(name="ToDelete")
    session.add(cat)
    session.commit()

    email = models.Email(
        gmail_id="uid-cascade",
        subject="Will stay",
        category_id=cat.id,
    )
    session.add(email)
    session.commit()

    session.delete(cat)
    session.commit()

    # Email should still exist but category_id should be NULL
    fetched = session.query(models.Email).filter_by(gmail_id="uid-cascade").first()
    assert fetched is not None
    assert fetched.category_id is None
    session.close()

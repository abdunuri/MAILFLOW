"""Unit tests for the email categorisation engine."""
import sys
import os

# Make sure backend modules are importable without installing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
from unittest.mock import MagicMock


def _make_category(
    id_=1,
    name="Test",
    sender_keywords="",
    subject_keywords="",
    body_keywords="",
    priority=0,
    color="#6366f1",
):
    """Create a mock Category ORM-like object."""
    cat = MagicMock()
    cat.id = id_
    cat.name = name
    cat.sender_keywords = sender_keywords
    cat.subject_keywords = subject_keywords
    cat.body_keywords = body_keywords
    cat.priority = priority
    cat.color = color
    return cat


class TestKeywordMatching:
    def test_simple_subject_match(self):
        from categorizer import categorize_email

        cat = _make_category(subject_keywords="invoice")
        email = {"sender": "someone@example.com", "subject": "Your Invoice #42", "body": ""}
        result = categorize_email(email, [cat])
        assert result is cat

    def test_no_match_returns_none(self):
        from categorizer import categorize_email

        cat = _make_category(subject_keywords="invoice")
        email = {"sender": "someone@example.com", "subject": "Hello world", "body": ""}
        result = categorize_email(email, [cat])
        assert result is None

    def test_sender_keyword_match(self):
        from categorizer import categorize_email

        cat = _make_category(sender_keywords="@github.com")
        email = {"sender": "noreply@github.com", "subject": "PR merged", "body": ""}
        result = categorize_email(email, [cat])
        assert result is cat

    def test_body_keyword_match(self):
        from categorizer import categorize_email

        cat = _make_category(body_keywords="unsubscribe")
        email = {
            "sender": "newsletter@example.com",
            "subject": "Weekly digest",
            "body": "Click here to unsubscribe.",
        }
        result = categorize_email(email, [cat])
        assert result is cat

    def test_case_insensitive(self):
        from categorizer import categorize_email

        cat = _make_category(subject_keywords="Invoice")
        email = {"sender": "a@b.com", "subject": "your invoice is ready", "body": ""}
        result = categorize_email(email, [cat])
        assert result is cat

    def test_multiple_keywords_any_matches(self):
        from categorizer import categorize_email

        cat = _make_category(subject_keywords="invoice, receipt, payment")
        email = {"sender": "a@b.com", "subject": "Your payment confirmed", "body": ""}
        result = categorize_email(email, [cat])
        assert result is cat

    def test_priority_order(self):
        """Higher-priority category wins when both rules match."""
        from categorizer import categorize_email

        low = _make_category(id_=1, name="Low", subject_keywords="invoice", priority=0)
        high = _make_category(id_=2, name="High", subject_keywords="invoice", priority=10)
        email = {"sender": "a@b.com", "subject": "Invoice #1", "body": ""}
        result = categorize_email(email, [low, high])
        assert result is high

    def test_empty_categories_returns_none(self):
        from categorizer import categorize_email

        email = {"sender": "a@b.com", "subject": "Hello", "body": ""}
        result = categorize_email(email, [])
        assert result is None

    def test_all_fields_must_match(self):
        """All non-empty rule fields must match for a category to apply."""
        from categorizer import categorize_email

        cat = _make_category(
            sender_keywords="@github.com",
            subject_keywords="merged",
        )
        # sender matches but subject does not
        email = {
            "sender": "noreply@github.com",
            "subject": "New follower",
            "body": "",
        }
        result = categorize_email(email, [cat])
        assert result is None

    def test_empty_keywords_treated_as_wildcard(self):
        """A category with NO rules matches everything (catch-all)."""
        from categorizer import categorize_email

        cat = _make_category(sender_keywords="", subject_keywords="", body_keywords="")
        email = {"sender": "anyone@example.com", "subject": "Anything", "body": ""}
        result = categorize_email(email, [cat])
        assert result is cat

    def test_comma_separated_keyword_parsing(self):
        from categorizer import _keywords

        assert _keywords("a, b, c") == ["a", "b", "c"]
        assert _keywords("  spaced  , keywords  ") == ["spaced", "keywords"]
        assert _keywords("") == []
        assert _keywords("single") == ["single"]

    def test_snippet_used_when_body_empty(self):
        """Falls back to snippet when body is absent."""
        from categorizer import categorize_email

        cat = _make_category(body_keywords="confirm")
        email = {
            "sender": "a@b.com",
            "subject": "Order",
            "body": "",
            "snippet": "Please confirm your order.",
        }
        result = categorize_email(email, [cat])
        assert result is cat


class TestApplyCategoriesHelper:
    def test_returns_list_with_matched_category(self):
        from categorizer import apply_categories_to_emails

        cat = _make_category(subject_keywords="test")
        emails = [{"sender": "a@b.com", "subject": "this is a test", "body": ""}]
        result = apply_categories_to_emails(emails, [cat])
        assert len(result) == 1
        assert result[0]["matched_category"] is cat

    def test_unmatched_email_gets_none_category(self):
        from categorizer import apply_categories_to_emails

        cat = _make_category(subject_keywords="invoice")
        emails = [{"sender": "a@b.com", "subject": "hello world", "body": ""}]
        result = apply_categories_to_emails(emails, [cat])
        assert result[0]["matched_category"] is None

"""Unit tests for Flask API endpoints (using Flask test client)."""
import sys
import os
import json
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret")


@pytest.fixture
def client(monkeypatch, tmp_path):
    """Return a Flask test client backed by an in-memory database."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("SECRET_KEY", "test-secret")

    import config
    config.DATABASE_URL = "sqlite:///:memory:"

    import importlib
    import models
    importlib.reload(models)
    models.init_db()

    import app as flask_app
    # Reset global singletons so they use the new in-memory DB
    flask_app.app.config["TESTING"] = True

    with flask_app.app.test_client() as c:
        yield c

    # teardown
    models._engine = None
    models._Session = None


# ---------------------------------------------------------------------------
# Category API
# ---------------------------------------------------------------------------

def test_list_categories_empty(client):
    res = client.get("/api/categories")
    assert res.status_code == 200
    assert res.get_json() == []


def test_create_category(client):
    payload = {
        "name": "Work",
        "description": "Work related",
        "color": "#ff0000",
        "subject_keywords": "meeting, project",
        "priority": 2,
    }
    res = client.post(
        "/api/categories",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert res.status_code == 201
    data = res.get_json()
    assert data["name"] == "Work"
    assert data["color"] == "#ff0000"
    assert data["priority"] == 2
    assert data.get("use_ai_reply") is False


def test_create_category_with_ai_reply(client):
    res = client.post(
        "/api/categories",
        data=json.dumps({"name": "AI Support", "use_ai_reply": True}),
        content_type="application/json",
    )
    assert res.status_code == 201
    assert res.get_json()["use_ai_reply"] is True


def test_create_category_missing_name(client):
    res = client.post(
        "/api/categories",
        data=json.dumps({"description": "no name"}),
        content_type="application/json",
    )
    assert res.status_code == 400


def test_update_category(client):
    # create
    res = client.post(
        "/api/categories",
        data=json.dumps({"name": "ToUpdate"}),
        content_type="application/json",
    )
    cat_id = res.get_json()["id"]

    # update
    res = client.put(
        f"/api/categories/{cat_id}",
        data=json.dumps({"name": "Updated", "priority": 5}),
        content_type="application/json",
    )
    assert res.status_code == 200
    assert res.get_json()["name"] == "Updated"
    assert res.get_json()["priority"] == 5


def test_delete_category(client):
    res = client.post(
        "/api/categories",
        data=json.dumps({"name": "ToDelete"}),
        content_type="application/json",
    )
    cat_id = res.get_json()["id"]

    res = client.delete(f"/api/categories/{cat_id}")
    assert res.status_code == 200

    res = client.get("/api/categories")
    assert all(c["id"] != cat_id for c in res.get_json())


def test_delete_nonexistent_category(client):
    res = client.delete("/api/categories/9999")
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Template API
# ---------------------------------------------------------------------------

def test_create_and_list_templates(client):
    # create category first
    cat_res = client.post(
        "/api/categories",
        data=json.dumps({"name": "Support"}),
        content_type="application/json",
    )
    cat_id = cat_res.get_json()["id"]

    res = client.post(
        "/api/templates",
        data=json.dumps({
            "category_id": cat_id,
            "name": "Ack",
            "body": "Thank you for reaching out.",
            "auto_reply": True,
        }),
        content_type="application/json",
    )
    assert res.status_code == 201
    tmpl = res.get_json()
    assert tmpl["auto_reply"] is True
    assert tmpl["category_id"] == cat_id

    # list
    res = client.get("/api/templates")
    assert res.status_code == 200
    assert len(res.get_json()) == 1


def test_create_template_missing_fields(client):
    res = client.post(
        "/api/templates",
        data=json.dumps({"name": "Incomplete"}),
        content_type="application/json",
    )
    assert res.status_code == 400


def test_update_template(client):
    cat_res = client.post(
        "/api/categories",
        data=json.dumps({"name": "Cat"}),
        content_type="application/json",
    )
    cat_id = cat_res.get_json()["id"]

    tmpl_res = client.post(
        "/api/templates",
        data=json.dumps({"category_id": cat_id, "name": "T", "body": "old body"}),
        content_type="application/json",
    )
    tmpl_id = tmpl_res.get_json()["id"]

    res = client.put(
        f"/api/templates/{tmpl_id}",
        data=json.dumps({"body": "new body", "auto_reply": True}),
        content_type="application/json",
    )
    assert res.status_code == 200
    assert res.get_json()["body"] == "new body"
    assert res.get_json()["auto_reply"] is True


def test_delete_template(client):
    cat_res = client.post(
        "/api/categories",
        data=json.dumps({"name": "CatX"}),
        content_type="application/json",
    )
    cat_id = cat_res.get_json()["id"]

    tmpl_res = client.post(
        "/api/templates",
        data=json.dumps({"category_id": cat_id, "name": "Tx", "body": "bye"}),
        content_type="application/json",
    )
    tmpl_id = tmpl_res.get_json()["id"]

    res = client.delete(f"/api/templates/{tmpl_id}")
    assert res.status_code == 200

    res = client.get("/api/templates")
    assert all(t["id"] != tmpl_id for t in res.get_json())


# ---------------------------------------------------------------------------
# Stats API
# ---------------------------------------------------------------------------

def test_stats_empty(client):
    res = client.get("/api/stats")
    assert res.status_code == 200
    data = res.get_json()
    assert data["total_emails"] == 0
    assert data["unread"] == 0
    assert data["replied"] == 0


# ---------------------------------------------------------------------------
# Auth API
# ---------------------------------------------------------------------------

def test_auth_status_not_authenticated(client):
    res = client.get("/auth/status")
    assert res.status_code == 200
    # token file does not exist in test environment
    assert res.get_json()["authenticated"] is False

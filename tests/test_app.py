import json

import pytest

from app import create_app


@pytest.fixture
def client():
    app = create_app(testing=True)
    with app.test_client() as client:
        yield client


def create_link(client, long_url, custom_alias=None):
    payload = {"long_url": long_url}
    if custom_alias:
        payload["custom_alias"] = custom_alias
    return client.post(
        "/api/links",
        data=json.dumps(payload),
        content_type="application/json",
    )


def test_create_link_success(client):
    resp = create_link(client, "https://example.com/some/page")
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["long_url"] == "https://example.com/some/page"
    assert len(data["short_code"]) == 6
    assert data["click_count"] == 0


def test_redirect_and_click_count_increment(client):
    resp = create_link(client, "https://example.com/redirect-target")
    short_code = resp.get_json()["short_code"]

    redirect_resp = client.get(f"/{short_code}", follow_redirects=False)
    assert redirect_resp.status_code == 302
    assert redirect_resp.headers["Location"] == "https://example.com/redirect-target"

    # click again to confirm increment
    client.get(f"/{short_code}", follow_redirects=False)

    stats_resp = client.get(f"/api/stats/{short_code}")
    assert stats_resp.status_code == 200
    assert stats_resp.get_json()["click_count"] == 2


def test_custom_alias_is_used(client):
    resp = create_link(client, "https://example.com/custom", custom_alias="myalias")
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["short_code"] == "myalias"

    redirect_resp = client.get("/myalias", follow_redirects=False)
    assert redirect_resp.status_code == 302
    assert redirect_resp.headers["Location"] == "https://example.com/custom"


def test_duplicate_alias_rejected(client):
    first = create_link(client, "https://example.com/first", custom_alias="taken")
    assert first.status_code == 201

    second = create_link(client, "https://example.com/second", custom_alias="taken")
    assert second.status_code == 409
    assert "error" in second.get_json()


def test_invalid_url_rejected(client):
    resp = create_link(client, "not-a-valid-url")
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_invalid_url_missing_scheme_rejected(client):
    resp = create_link(client, "example.com/no-scheme")
    assert resp.status_code == 400


def test_unknown_short_code_404s(client):
    resp = client.get("/doesnotexist")
    assert resp.status_code == 404


def test_index_page_lists_links(client):
    create_link(client, "https://example.com/listed")
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"example.com/listed" in resp.data

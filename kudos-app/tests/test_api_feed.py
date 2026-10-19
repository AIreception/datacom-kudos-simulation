"""Employee feed filtering, ordering, and pagination tests."""

from __future__ import annotations

import pytest

from tests.helpers import (
    execute,
    fetch_one,
    insert_kudos,
    login,
)


def error_code(response) -> str:
    return response.get_json()["error"]["code"]


def feed(client) -> dict:
    response = client.get("/api/kudos")
    assert response.status_code == 200, response.get_json()
    return response.get_json()


def test_feed_requires_a_session(client):
    response = client.get("/api/kudos")
    assert response.status_code == 401
    assert error_code(response) == "UNAUTHENTICATED"


def test_feed_is_newest_first(client, app, employee_id, colleague_id):
    login(client, employee_id)
    oldest = insert_kudos(
        app,
        employee_id,
        colleague_id,
        "Oldest",
        created_at="2026-01-01T09:00:00.000Z",
    )
    newest = insert_kudos(
        app,
        employee_id,
        colleague_id,
        "Newest",
        created_at="2026-01-03T09:00:00.000Z",
    )
    middle = insert_kudos(
        app,
        employee_id,
        colleague_id,
        "Middle",
        created_at="2026-01-02T09:00:00.000Z",
    )

    data = feed(client)
    assert [item["id"] for item in data["items"]] == [newest, middle, oldest]
    assert [item["message"] for item in data["items"]] == [
        "Newest",
        "Middle",
        "Oldest",
    ]


def test_feed_breaks_timestamp_ties_by_id_descending(
    client, app, employee_id, colleague_id
):
    login(client, employee_id)
    timestamp = "2026-02-01T10:00:00.000Z"
    first = insert_kudos(
        app, employee_id, colleague_id, "First", created_at=timestamp
    )
    second = insert_kudos(
        app, employee_id, colleague_id, "Second", created_at=timestamp
    )

    items = feed(client)["items"]
    assert [item["id"] for item in items] == [second, first]


def test_feed_excludes_hidden_kudos(
    client, app, employee_id, colleague_id
):
    login(client, employee_id)
    visible = insert_kudos(app, employee_id, colleague_id, "Visible")
    insert_kudos(app, employee_id, colleague_id, "Hidden", is_visible=0)

    items = feed(client)["items"]
    assert [item["id"] for item in items] == [visible]
    assert all(item["message"] != "Hidden" for item in items)


def test_feed_excludes_rows_deleted_from_the_database(
    client, app, employee_id, colleague_id
):
    login(client, employee_id)
    kept = insert_kudos(app, employee_id, colleague_id, "Kept")
    removed = insert_kudos(app, employee_id, colleague_id, "Removed")
    execute(app, "DELETE FROM kudos WHERE id = ?", (removed,))

    items = feed(client)["items"]
    assert [item["id"] for item in items] == [kept]


def test_feed_item_shape_omits_moderation_and_private_fields(
    client, app, employee_id, colleague_id
):
    login(client, employee_id)
    insert_kudos(app, employee_id, colleague_id, "Shape check")

    item = feed(client)["items"][0]
    assert set(item) == {"id", "message", "createdAt", "giver", "recipient"}
    assert set(item["giver"]) == {"id", "name"}
    assert set(item["recipient"]) == {"id", "name"}
    assert "isVisible" not in item


def test_feed_defaults_to_twenty_items_and_reports_more(
    client, app, employee_id, colleague_id
):
    login(client, employee_id)
    for index in range(21):
        insert_kudos(
            app,
            employee_id,
            colleague_id,
            f"Item {index}",
            created_at=f"2026-03-01T09:{index:02d}:00.000Z",
        )

    data = feed(client)
    assert len(data["items"]) == 20
    assert data["pagination"] == {
        "limit": 20,
        "offset": 0,
        "hasMore": True,
        "nextOffset": 20,
    }
    assert data["items"][0]["message"] == "Item 20"


def test_feed_pagination_walks_all_items_without_duplicates(
    client, app, employee_id, colleague_id
):
    login(client, employee_id)
    ids = [
        insert_kudos(app, employee_id, colleague_id, f"Item {index}")
        for index in range(5)
    ]

    seen = []
    offset = 0
    while True:
        response = client.get(f"/api/kudos?limit=2&offset={offset}")
        assert response.status_code == 200
        data = response.get_json()
        seen.extend(item["id"] for item in data["items"])
        if not data["pagination"]["hasMore"]:
            break
        offset = data["pagination"]["nextOffset"]

    assert seen == list(reversed(ids))
    assert len(seen) == len(set(seen)) == 5


def test_feed_offset_beyond_the_end_returns_an_empty_page(
    client, app, employee_id, colleague_id
):
    login(client, employee_id)
    insert_kudos(app, employee_id, colleague_id, "Only one")

    data = client.get("/api/kudos?offset=100").get_json()
    assert data["items"] == []
    assert data["pagination"] == {
        "limit": 20,
        "offset": 100,
        "hasMore": False,
        "nextOffset": None,
    }


def test_feed_accepts_the_maximum_page_size(
    client, app, employee_id, colleague_id
):
    login(client, employee_id)
    insert_kudos(app, employee_id, colleague_id, "Only one")

    data = client.get("/api/kudos?limit=50").get_json()
    assert data["pagination"]["limit"] == 50
    assert data["pagination"]["hasMore"] is False


@pytest.mark.parametrize("query", ["limit=0", "limit=51", "limit=abc", "limit=-1"])
def test_feed_rejects_invalid_limits(client, employee_id, query):
    login(client, employee_id)
    response = client.get(f"/api/kudos?{query}")
    assert response.status_code == 400
    assert error_code(response) == "VALIDATION_ERROR"
    assert "limit" in response.get_json()["error"]["fields"]


@pytest.mark.parametrize("query", ["offset=-1", "offset=abc", "offset=1.5"])
def test_feed_rejects_invalid_offsets(client, employee_id, query):
    login(client, employee_id)
    response = client.get(f"/api/kudos?{query}")
    assert response.status_code == 400
    assert error_code(response) == "VALIDATION_ERROR"
    assert "offset" in response.get_json()["error"]["fields"]


def test_feed_returns_empty_list_when_no_visible_kudos_exist(
    client, app, employee_id, colleague_id
):
    login(client, employee_id)
    insert_kudos(app, employee_id, colleague_id, "Hidden", is_visible=0)

    data = feed(client)
    assert data["items"] == []
    assert data["pagination"]["hasMore"] is False
    count = fetch_one(
        app,
        "SELECT COUNT(*) AS count FROM kudos WHERE is_visible = 1",
    )["count"]
    assert count == 0

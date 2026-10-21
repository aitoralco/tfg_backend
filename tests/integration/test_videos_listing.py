"""Home page previews, public search and the user's own library."""

import base64
from datetime import datetime

import pytest

from support import FAKE_JPEG


def titles(response):
    return [p["title"] for p in response.json()["previews"]]


class TestPreviews:
    def test_only_shared_videos_are_listed(self, client, make_video, user):
        make_video(user, title="public", shared=True)
        make_video(user, title="private", shared=False)

        response = client.get("/videos/previews")

        assert response.status_code == 200
        assert titles(response) == ["public"]
        assert response.json()["total"] == 1

    def test_preview_record_shape(self, client, make_video, user):
        video = make_video(user, title="Orca", description="Pod of five", thumbnail=FAKE_JPEG)

        [preview] = client.get("/videos/previews").json()["previews"]

        assert preview == {
            "id": video.id,
            "title": "Orca",
            "description": "Pod of five",
            "file_name": video.file_name,
            "uploader": "alice",
            "created_at": video.created_at.isoformat(),
            "status": {"id": 2, "status_name": "unprocessed"},
            "shared": True,
            "preview": base64.b64encode(FAKE_JPEG).decode("ascii"),
        }

    def test_preview_is_null_without_thumbnail(self, client, make_video, user):
        make_video(user)

        [preview] = client.get("/videos/previews").json()["previews"]

        assert preview["preview"] is None

    def test_pagination(self, client, make_video, user):
        for i in range(5):
            make_video(user, title=f"v{i}")

        response = client.get("/videos/previews", params={"offset": 2, "limit": 2})

        assert titles(response) == ["v2", "v3"]
        assert response.json() | {"previews": None} == {"previews": None, "total": 5, "offset": 2, "limit": 2}

    def test_limit_is_capped_at_50(self, client):
        assert client.get("/videos/previews", params={"limit": 1000}).json()["limit"] == 50

    def test_filter_by_user(self, client, make_video, user, other_user):
        make_video(user, title="mine")
        make_video(other_user, title="theirs")

        response = client.get("/videos/previews", params={"user_id": other_user.id})

        assert titles(response) == ["theirs"]


class TestSearch:
    @pytest.fixture(autouse=True)
    def catalog(self, make_video, user, other_user):
        make_video(user, title="Blue whale", description="Biggest animal", created_at=datetime(2026, 1, 10))
        make_video(user, title="Dolphins", description="Playing with a WHALE shark", created_at=datetime(2026, 2, 10))
        make_video(other_user, title="Sperm whale", description=None, created_at=datetime(2026, 3, 10))
        make_video(other_user, title="Secret whale", shared=False, created_at=datetime(2026, 3, 11))

    def search(self, client, **params):
        return client.get("/videos/search", params=params)

    def test_no_filters_returns_shared_videos_newest_first(self, client):
        response = self.search(client)

        assert titles(response) == ["Sperm whale", "Dolphins", "Blue whale"]
        assert response.json()["total"] == 3

    def test_text_matches_title_or_description_ignoring_case(self, client):
        assert titles(self.search(client, q="WhAlE")) == ["Sperm whale", "Dolphins", "Blue whale"]
        assert titles(self.search(client, q="animal")) == ["Blue whale"]

    def test_private_videos_are_never_found(self, client):
        assert titles(self.search(client, q="secret")) == []

    def test_by_partial_uploader_name(self, client):
        assert titles(self.search(client, uploader="BO")) == ["Sperm whale"]

    def test_by_date_range(self, client):
        response = self.search(client, date_from="2026-02-01", date_to="2026-03-01")

        assert titles(response) == ["Dolphins"]

    def test_filters_are_combined(self, client):
        assert titles(self.search(client, q="whale", uploader="alice", date_from="2026-02-01")) == ["Dolphins"]

    def test_total_ignores_pagination(self, client):
        response = self.search(client, limit=1, offset=1)

        assert titles(response) == ["Dolphins"]
        assert response.json()["total"] == 3

    def test_results_skip_thumbnails(self, client):
        assert all(p["preview"] is None for p in self.search(client).json()["previews"])

    @pytest.mark.parametrize("param", ["date_from", "date_to"])
    def test_invalid_date_is_400(self, client, param):
        response = self.search(client, **{param: "10/02/2026"})

        assert response.status_code == 400
        assert param in response.json()["detail"]


class TestMine:
    @pytest.fixture(autouse=True)
    def library(self, make_video, user, other_user):
        make_video(user, title="b-public", shared=True, status="processed", created_at=datetime(2026, 1, 1))
        make_video(user, title="a-private", shared=False, created_at=datetime(2026, 2, 1))
        make_video(user, title="c-error", description="corrupted file", status="error", created_at=datetime(2026, 3, 1))
        make_video(other_user, title="not mine", created_at=datetime(2026, 4, 1))

    def mine(self, client, headers, **params):
        return client.get("/videos/mine", headers=headers, params=params)

    def test_lists_own_videos_including_private_newest_first(self, client, user, auth_headers):
        response = self.mine(client, auth_headers(user))

        assert response.status_code == 200
        assert titles(response) == ["c-error", "a-private", "b-public"]

    def test_requires_credentials(self, client):
        assert client.get("/videos/mine").status_code == 403

    def test_text_filter(self, client, user, auth_headers):
        assert titles(self.mine(client, auth_headers(user), q="CORRUPTED")) == ["c-error"]

    def test_status_filter(self, client, user, auth_headers):
        processed_id = 7
        assert titles(self.mine(client, auth_headers(user), status_id=processed_id)) == ["b-public"]

    def test_date_filter(self, client, user, auth_headers):
        response = self.mine(client, auth_headers(user), date_from="2026-01-15", date_to="2026-02-15")

        assert titles(response) == ["a-private"]

    @pytest.mark.parametrize(
        "sort_by, order, expected",
        [
            ("title", "asc", ["a-private", "b-public", "c-error"]),
            ("title", "desc", ["c-error", "b-public", "a-private"]),
            ("created_at", "asc", ["b-public", "a-private", "c-error"]),
            ("unknown", "asc", ["b-public", "a-private", "c-error"]),  # falls back to created_at
        ],
    )
    def test_sorting(self, client, user, auth_headers, sort_by, order, expected):
        assert titles(self.mine(client, auth_headers(user), sort_by=sort_by, order=order)) == expected

    def test_pagination(self, client, user, auth_headers):
        response = self.mine(client, auth_headers(user), offset=1, limit=1)

        assert titles(response) == ["a-private"]
        assert response.json()["total"] == 3

    def test_invalid_date_is_400(self, client, user, auth_headers):
        assert self.mine(client, auth_headers(user), date_from="yesterday").status_code == 400


@pytest.mark.xfail(reason="Pagination params are not validated: negative values reach the SQL query (500 on Postgres)")
@pytest.mark.parametrize("params", [{"offset": -1}, {"limit": -1}, {"limit": 0}])
@pytest.mark.parametrize("path", ["/videos/previews", "/videos/search"])
def test_invalid_pagination_is_422(client_no_raise, path, params):
    assert client_no_raise.get(path, params=params).status_code == 422

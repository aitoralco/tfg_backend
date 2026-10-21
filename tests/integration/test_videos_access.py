"""Who can see what: shared videos are public, private ones only for their owner and admins."""

import pytest

from app.core.security import create_access_token

CONTENT = bytes(range(256)) * 4  # 1024 bytes

# Every endpoint that exposes a single video by id
VIDEO_ENDPOINTS = [
    "/videos/{id}",
    "/videos/{id}/info",
    "/videos/{id}/dw/stream",
    "/videos/{id}/ew/crops",
    "/videos/{id}/dem/crops",
]


@pytest.fixture
def private_video(make_video, user, storage):
    video = make_video(user, shared=False, content=CONTENT)
    # Processing results so every endpoint has something to serve
    base = f"{user.id}/{video.group_id}/{video.id}"
    storage.put(f"{base}/dw/annotated.avi", b"dw-video")
    storage.put(f"{base}/ew/crop_0.jpg", b"crop")
    storage.put(f"{base}/dem/crop_0.jpg", b"crop")
    return video


class TestVisibility:
    @pytest.mark.parametrize("endpoint", VIDEO_ENDPOINTS)
    def test_anonymous_cannot_see_private_videos(self, client, private_video, endpoint):
        response = client.get(endpoint.format(id=private_video.id))

        assert response.status_code == 404

    @pytest.mark.parametrize("endpoint", VIDEO_ENDPOINTS)
    def test_other_users_cannot_see_private_videos(self, client, private_video, other_user, auth_headers, endpoint):
        response = client.get(endpoint.format(id=private_video.id), headers=auth_headers(other_user))

        assert response.status_code == 404

    @pytest.mark.parametrize("endpoint", VIDEO_ENDPOINTS)
    def test_owner_sees_own_private_videos(self, client, private_video, user, auth_headers, endpoint):
        response = client.get(endpoint.format(id=private_video.id), headers=auth_headers(user))

        assert response.status_code == 200

    @pytest.mark.parametrize("endpoint", VIDEO_ENDPOINTS)
    def test_admin_sees_private_videos(self, client, private_video, admin, auth_headers, endpoint):
        response = client.get(endpoint.format(id=private_video.id), headers=auth_headers(admin))

        assert response.status_code == 200

    @pytest.mark.parametrize("endpoint", VIDEO_ENDPOINTS)
    def test_owner_can_authenticate_with_query_token(self, client, private_video, user, endpoint):
        # <video src> cannot send headers, so the frontend appends ?token=
        token = create_access_token(user.id, user.role.name)

        response = client.get(endpoint.format(id=private_video.id), params={"token": token})

        assert response.status_code == 200

    def test_private_and_missing_videos_are_indistinguishable(self, client, private_video):
        private = client.get(f"/videos/{private_video.id}/info")
        missing = client.get("/videos/9999/info")

        assert private.status_code == missing.status_code == 404
        assert private.json() == missing.json()

    def test_shared_videos_are_public(self, client, make_video, user):
        video = make_video(user, shared=True, content=CONTENT)

        assert client.get(f"/videos/{video.id}").status_code == 200

    def test_invalid_token_is_treated_as_anonymous(self, client, make_video, user):
        shared = make_video(user, shared=True, content=CONTENT)
        private = make_video(user, shared=False, content=CONTENT)
        headers = {"Authorization": "Bearer garbage"}

        assert client.get(f"/videos/{shared.id}", headers=headers).status_code == 200
        assert client.get(f"/videos/{private.id}", headers=headers).status_code == 404


class TestStreaming:
    @pytest.fixture
    def video(self, make_video, user):
        return make_video(user, shared=True, content=CONTENT)

    def test_without_range_returns_whole_file(self, client, video):
        response = client.get(f"/videos/{video.id}")

        assert response.status_code == 200
        assert response.content == CONTENT
        assert response.headers["content-type"] == "video/mp4"
        assert response.headers["accept-ranges"] == "bytes"
        assert response.headers["content-length"] == str(len(CONTENT))

    @pytest.mark.parametrize(
        "range_header, start, end",
        [
            ("bytes=0-99", 0, 99),
            ("bytes=1000-", 1000, 1023),
            ("bytes=-24", 1000, 1023),
        ],
    )
    def test_range_returns_partial_content(self, client, video, range_header, start, end):
        response = client.get(f"/videos/{video.id}", headers={"Range": range_header})

        assert response.status_code == 206
        assert response.content == CONTENT[start : end + 1]
        assert response.headers["content-range"] == f"bytes {start}-{end}/{len(CONTENT)}"
        assert response.headers["content-length"] == str(end - start + 1)

    def test_malformed_range_is_400(self, client, video):
        assert client.get(f"/videos/{video.id}", headers={"Range": "lines=1-2"}).status_code == 400

    def test_unsatisfiable_range_is_416(self, client, video):
        assert client.get(f"/videos/{video.id}", headers={"Range": "bytes=5000-"}).status_code == 416

    def test_missing_video_is_404(self, client):
        assert client.get("/videos/9999").status_code == 404

    def test_file_missing_from_storage_is_404(self, client, make_video, user):
        video = make_video(user, shared=True)  # row without object in the bucket

        response = client.get(f"/videos/{video.id}")

        assert response.status_code == 404
        assert response.json()["detail"] == "Video not found in storage"

    def test_video_without_file_name_is_404(self, client, db, video):
        video.file_name = None
        db.commit()

        response = client.get(f"/videos/{video.id}")

        assert response.status_code == 404
        assert response.json()["detail"] == "Video file not available"

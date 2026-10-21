"""Owners editing and deleting their videos."""

import pytest

from app.filesystem import FileSystemClient
from app.models import VideoModel


@pytest.fixture
def video(make_video, user, storage):
    video = make_video(user, title="Original", description="Original description", shared=False, content=b"data")
    storage.put(f"{user.id}/{video.group_id}/thumbnail.jpg", b"jpeg")
    storage.put(f"{user.id}/{video.group_id}/{video.id}/dw/out.avi", b"dw")
    return video


def find_video(db, video_id):
    return db.query(VideoModel).filter_by(id=video_id).one_or_none()


class TestUpdate:
    def test_owner_updates_every_editable_field(self, client, db, video, user, auth_headers):
        response = client.patch(
            f"/videos/{video.id}",
            headers=auth_headers(user),
            json={"title": "New", "description": "New description", "shared": True},
        )

        assert response.status_code == 200
        body = response.json()
        assert (body["title"], body["description"], body["shared"]) == ("New", "New description", True)
        db.refresh(video)
        assert (video.title, video.description, video.shared) == ("New", "New description", True)

    def test_partial_update_keeps_other_fields(self, client, db, video, user, auth_headers):
        client.patch(f"/videos/{video.id}", headers=auth_headers(user), json={"shared": True})

        db.refresh(video)
        assert (video.title, video.description, video.shared) == ("Original", "Original description", True)

    def test_owner_and_status_cannot_be_changed(self, client, db, video, user, other_user, auth_headers):
        client.patch(
            f"/videos/{video.id}",
            headers=auth_headers(user),
            json={"user_id": other_user.id, "status_id": 7, "id": 999},
        )

        db.refresh(video)
        assert (video.user_id, video.status.status_name) == (user.id, "unprocessed")

    def test_other_user_is_403_and_nothing_changes(self, client, db, video, other_user, auth_headers):
        response = client.patch(f"/videos/{video.id}", headers=auth_headers(other_user), json={"title": "Hacked"})

        assert response.status_code == 403
        db.refresh(video)
        assert video.title == "Original"

    def test_missing_video_is_404(self, client, user, auth_headers):
        assert client.patch("/videos/9999", headers=auth_headers(user), json={"title": "x"}).status_code == 404

    def test_requires_credentials(self, client, video):
        assert client.patch(f"/videos/{video.id}", json={"title": "x"}).status_code == 403


class TestDelete:
    def test_owner_deletes_row_and_every_stored_file(self, client, db, video, user, auth_headers, storage, make_video):
        neighbour = make_video(user, content=b"keep me")

        response = client.delete(f"/videos/{video.id}", headers=auth_headers(user))

        assert response.status_code == 204
        assert find_video(db, video.id) is None
        assert storage.keys() == [f"{user.id}/{neighbour.group_id}/{neighbour.file_name}"]

    def test_other_user_is_403_and_nothing_is_deleted(self, client, db, video, user, other_user, auth_headers, storage):
        files_before = storage.keys()

        response = client.delete(f"/videos/{video.id}", headers=auth_headers(other_user))

        assert response.status_code == 403
        assert find_video(db, video.id) is not None
        assert storage.keys() == files_before

    def test_missing_video_is_404(self, client, user, auth_headers):
        assert client.delete("/videos/9999", headers=auth_headers(user)).status_code == 404

    def test_requires_credentials(self, client, db, video):
        assert client.delete(f"/videos/{video.id}").status_code == 403
        assert find_video(db, video.id) is not None

    def test_storage_failure_still_deletes_the_row(self, client, db, video, user, auth_headers, monkeypatch):
        def broken_delete(self, user_id, group_id):
            raise ConnectionError("minio down")

        monkeypatch.setattr(FileSystemClient, "delete_group", broken_delete)

        response = client.delete(f"/videos/{video.id}", headers=auth_headers(user))

        assert response.status_code == 204
        assert find_video(db, video.id) is None

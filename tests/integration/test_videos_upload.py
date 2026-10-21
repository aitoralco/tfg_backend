import os

import pytest

from app.filesystem import FileSystemClient
from app.models import VideoModel
from support import FAKE_JPEG

VIDEO_BYTES = b"\x00\x00\x00\x18ftypmp42" + b"\x01" * 2048


def upload(client, headers, filename="whale.mp4", content=VIDEO_BYTES, **form):
    data = {"video_name": "Humpback", "description": "Seen off the coast", **form}
    return client.post("/videos/upload", headers=headers, data=data, files={"file": (filename, content, "video/mp4")})


def test_creates_the_video_row(client, db, user, auth_headers):
    response = upload(client, auth_headers(user))

    assert response.status_code == 201
    assert response.json()["message"] == "Video uploaded successfully"
    video = db.get(VideoModel, response.json()["video_id"])
    assert video.user_id == user.id
    assert video.title == "Humpback"
    assert video.description == "Seen off the coast"
    assert video.status.status_name == "unprocessed"
    assert video.shared is False
    assert video.group_id == video.id


def test_stores_the_file_under_a_random_name_keeping_the_extension(client, db, user, auth_headers, storage):
    response = upload(client, auth_headers(user), filename="my holiday.MP4")

    video = db.get(VideoModel, response.json()["video_id"])
    assert video.file_name.endswith(".MP4")
    assert video.file_name != "my holiday.MP4"
    assert storage.get(f"{user.id}/{video.group_id}/{video.file_name}") == VIDEO_BYTES


def test_file_names_are_unique_across_uploads(client, db, user, auth_headers):
    ids = [upload(client, auth_headers(user)).json()["video_id"] for _ in range(2)]

    assert db.get(VideoModel, ids[0]).file_name != db.get(VideoModel, ids[1]).file_name


def test_stores_the_thumbnail_made_by_ffmpeg(client, user, auth_headers, storage, ffmpeg):
    video_id = upload(client, auth_headers(user)).json()["video_id"]

    assert storage.get(f"{user.id}/{video_id}/thumbnail.jpg") == FAKE_JPEG
    [cmd] = ffmpeg.calls
    assert cmd[0] == "ffmpeg"
    assert cmd[cmd.index("-frames:v") + 1] == "1"


def test_ffmpeg_failure_does_not_block_the_upload(client, user, auth_headers, storage, ffmpeg):
    ffmpeg.returncode = 1

    response = upload(client, auth_headers(user))

    assert response.status_code == 201
    video_id = response.json()["video_id"]
    assert storage.keys(f"{user.id}/{video_id}/thumbnail") == []


def test_enqueues_the_processing_job(client, user, auth_headers, job_queue):
    video_id = upload(client, auth_headers(user)).json()["video_id"]

    [job] = job_queue.jobs
    assert job.func_name == "app.cache_redis.tasks.process_video"
    assert job.args == (video_id,)


def test_temporary_files_are_removed(client, user, auth_headers, ffmpeg):
    upload(client, auth_headers(user))

    [cmd] = ffmpeg.calls
    video_tmp, thumb_tmp = cmd[cmd.index("-i") + 1], cmd[-1]
    assert not os.path.exists(video_tmp)
    assert not os.path.exists(thumb_tmp)


def test_requires_credentials(client, db):
    assert upload(client, headers={}).status_code == 403
    assert db.query(VideoModel).count() == 0


@pytest.mark.parametrize("missing", ["video_name", "description"])
def test_missing_form_field_is_422(client, user, auth_headers, missing):
    data = {"video_name": "t", "description": "d"}
    del data[missing]

    response = client.post(
        "/videos/upload", headers=auth_headers(user), data=data, files={"file": ("a.mp4", b"x", "video/mp4")}
    )

    assert response.status_code == 422


def test_missing_file_is_422(client, user, auth_headers):
    response = client.post("/videos/upload", headers=auth_headers(user), data={"video_name": "t", "description": "d"})

    assert response.status_code == 422


def test_storage_failure_is_500_and_leaves_no_row(client, db, user, auth_headers, monkeypatch, job_queue):
    def broken_upload(self, **kwargs):
        raise ConnectionError("minio down")

    monkeypatch.setattr(FileSystemClient, "upload_video_stream", broken_upload)

    response = upload(client, auth_headers(user))

    assert response.status_code == 500
    assert "Error saving video to storage" in response.json()["detail"]
    assert db.query(VideoModel).count() == 0
    assert job_queue.count == 0


@pytest.fixture
def broken_redis(monkeypatch):
    from app.cache_redis.redis_engine import RedisEngine

    def broken_enqueue(self, function, video_id):
        raise ConnectionError("redis down")

    monkeypatch.setattr(RedisEngine, "enqueue_job", broken_enqueue)


def test_queue_failure_is_500_and_leaves_no_row(client, db, user, auth_headers, broken_redis):
    response = upload(client, auth_headers(user))

    assert response.status_code == 500
    assert "Error queueing video for processing" in response.json()["detail"]
    assert db.query(VideoModel).count() == 0


@pytest.mark.xfail(reason="The DB row is rolled back but the file already uploaded to MinIO is left orphaned")
def test_queue_failure_does_not_leave_orphan_files(client, user, auth_headers, storage, broken_redis):
    upload(client, auth_headers(user))

    assert storage.keys() == []

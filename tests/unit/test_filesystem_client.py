import io
from urllib.parse import urlparse

import pytest

from app.core.config import settings
from app.filesystem import FileSystemClient


@pytest.fixture
def fs():
    return FileSystemClient()


def test_creates_the_bucket_when_missing(s3, monkeypatch):
    monkeypatch.setattr(settings, "BUCKET_NAME", "brand-new-bucket")

    FileSystemClient()

    assert "brand-new-bucket" in [b["Name"] for b in s3.list_buckets()["Buckets"]]


def test_upload_video_stream_stores_under_user_and_group(fs, s3, storage):
    fs.upload_video_stream(io.BytesIO(b"video-bytes"), "clip.mp4", user_id=7, group_id=3)

    assert storage.get("7/3/clip.mp4") == b"video-bytes"
    head = s3.head_object(Bucket=settings.BUCKET_NAME, Key="7/3/clip.mp4")
    assert head["ContentType"] == "video/mp4"


def test_object_size(fs, storage):
    storage.put("1/2/clip.mp4", b"x" * 1234)

    assert fs.get_object_size(1, 2, "clip.mp4") == 1234


def test_object_range_is_inclusive(fs, storage):
    storage.put("1/2/clip.mp4", b"0123456789")

    assert b"".join(fs.get_object_range(1, 2, "clip.mp4", 2, 5)) == b"2345"


def test_object_range_by_key(fs, storage):
    storage.put("1/2/2/dw/out.avi", b"0123456789")

    assert b"".join(fs.get_object_range_by_key("1/2/2/dw/out.avi", 7, 9)) == b"789"


def test_first_bytes(fs, storage):
    storage.put("1/2/clip.mp4", b"0123456789")

    assert fs.get_object_first_bytes(1, 2, "clip.mp4", 4) == b"0123"
    assert fs.get_object_first_bytes(1, 2, "missing.mp4", 4) == b""


def test_thumbnail_round_trip(fs, storage):
    assert fs.get_thumbnail(1, 2) == b""

    fs.upload_thumbnail(b"jpeg", user_id=1, group_id=2)

    assert storage.get("1/2/thumbnail.jpg") == b"jpeg"
    assert fs.get_thumbnail(1, 2) == b"jpeg"


def test_get_object_bytes_returns_none_when_missing(fs, storage):
    storage.put("a/b.json", b"{}")

    assert fs.get_object_bytes("a/b.json") == b"{}"
    assert fs.get_object_bytes("a/missing.json") is None


def test_list_objects_with_prefix_skips_directory_markers_and_other_prefixes(fs, storage):
    storage.put("1/2/2/ew/", b"")
    storage.put("1/2/2/ew/a.jpg", b"aa")
    storage.put("1/2/2/ew/sub/b.png", b"b")
    storage.put("1/2/2/dem/c.jpg", b"c")

    objects = fs.list_objects_with_prefix("1/2/2/ew/")

    assert sorted(objects, key=lambda o: o["key"]) == [
        {"key": "1/2/2/ew/a.jpg", "size": 2},
        {"key": "1/2/2/ew/sub/b.png", "size": 1},
    ]


def test_presigned_url_points_to_the_public_endpoint(fs):
    url = urlparse(fs.generate_presigned_url("1/2/2/ew/a.jpg", expiry=60))

    assert f"{url.scheme}://{url.netloc}" == settings.FILESYSTEM_PUBLIC_URL
    assert url.path == f"/{settings.BUCKET_NAME}/1/2/2/ew/a.jpg"
    assert "X-Amz-Expires=60" in url.query


def test_delete_group_only_removes_that_group(fs, storage):
    storage.put("1/1/clip.mp4", b"x")
    storage.put("1/1/thumbnail.jpg", b"x")
    storage.put("1/1/1/dw/out.avi", b"x")
    storage.put("1/10/clip.mp4", b"x")  # same prefix text, different group
    storage.put("2/1/clip.mp4", b"x")

    fs.delete_group(user_id=1, group_id=1)

    assert storage.keys() == ["1/10/clip.mp4", "2/1/clip.mp4"]


def test_delete_object(fs, storage):
    storage.put("1/1/clip.mp4", b"x")

    fs.delete_object(1, 1, "clip.mp4")

    assert storage.keys() == []

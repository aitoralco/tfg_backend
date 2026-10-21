"""Results written to MinIO by the worker: DW video, EW/DEM crops and classification."""

import base64
import json
from urllib.parse import urlparse

import pytest

from app.core.config import settings
from support import FAKE_JPEG

CLASSIFICATION = {
    "total_images": 10,
    "classified_images": 9,
    "errors": 1,
    "classes": {"humpback": {"count": 9, "percentage": 100.0, "avg_confidence": 0.93}},
}


@pytest.fixture
def video(make_video, user):
    return make_video(user, shared=True, status="processed", thumbnail=FAKE_JPEG)


@pytest.fixture
def results(video, storage):
    """Writes objects under the video's results prefix: {user_id}/{group_id}/{video_id}/..."""
    base = f"{video.user_id}/{video.group_id}/{video.id}"

    def put(path, body=b"x"):
        storage.put(f"{base}/{path}", body)
        return f"{base}/{path}"

    return put


class TestInfo:
    def test_video_without_results(self, client, video):
        response = client.get(f"/videos/{video.id}/info")

        assert response.status_code == 200
        body = response.json()
        assert body["title"] == video.title
        assert body["uploader"] == "alice"
        assert body["status"] == {"id": 7, "status_name": "processed"}
        assert body["thumbnail"] == base64.b64encode(FAKE_JPEG).decode("ascii")
        assert body["dw"] == {"available": False, "video_key": None, "label_count": 0}
        assert body["ew"] == {"available": False, "crop_count": 0}
        assert body["dem"] == {"available": False, "txt_count": 0, "crop_count": 0}
        assert body["classification"] is None

    def test_summarises_every_phase(self, client, video, results):
        dw_key = results("dw/annotated.avi")
        results("dw/labels/frame_1.txt")
        results("dw/labels/frame_2.txt")
        results("ew/crop_1.jpg")
        results("ew/crop_2.PNG")
        results("ew/metadata.csv")  # not a crop
        results("dem/crop_1.jpg")
        results("dem/marks_1.txt")
        results("dem/marks_2.txt")
        results("classification.json", json.dumps(CLASSIFICATION).encode())

        body = client.get(f"/videos/{video.id}/info").json()

        assert body["dw"] == {"available": True, "video_key": dw_key, "label_count": 2}
        assert body["ew"] == {"available": True, "crop_count": 2}
        assert body["dem"] == {"available": True, "txt_count": 2, "crop_count": 1}
        assert body["classification"] == CLASSIFICATION

    def test_ignores_results_of_other_videos(self, client, video, make_video, user, storage):
        other = make_video(user)
        storage.put(f"{user.id}/{other.group_id}/{other.id}/ew/crop.jpg", b"x")

        assert client.get(f"/videos/{video.id}/info").json()["ew"]["available"] is False

    def test_corrupted_classification_is_ignored(self, client, video, results):
        results("classification.json", b"{not json")

        response = client.get(f"/videos/{video.id}/info")

        assert response.status_code == 200
        assert response.json()["classification"] is None

    def test_missing_video_is_404(self, client):
        assert client.get("/videos/9999/info").status_code == 404


class TestDWStream:
    def test_404_until_the_worker_produces_it(self, client, video, results):
        results("dw/labels/frame_1.txt")

        response = client.get(f"/videos/{video.id}/dw/stream")

        assert response.status_code == 404
        assert response.json()["detail"] == "DW video not available yet"

    def test_streams_the_annotated_video(self, client, video, results):
        results("dw/annotated.mp4", b"0123456789")

        response = client.get(f"/videos/{video.id}/dw/stream")

        assert response.status_code == 200
        assert response.content == b"0123456789"
        assert response.headers["content-type"].startswith("video/")

    def test_supports_range_requests(self, client, video, results):
        results("dw/annotated.mp4", b"0123456789")

        response = client.get(f"/videos/{video.id}/dw/stream", headers={"Range": "bytes=2-4"})

        assert response.status_code == 206
        assert response.content == b"234"
        assert response.headers["content-range"] == "bytes 2-4/10"


@pytest.mark.parametrize("phase", ["ew", "dem"])
class TestCrops:
    def test_returns_presigned_urls_sorted_by_key(self, client, video, results, phase):
        keys = [results(f"{phase}/crop_{n}.jpg") for n in (3, 1, 2)]
        results(f"{phase}/notes.txt")  # not an image

        body = client.get(f"/videos/{video.id}/{phase}/crops").json()

        assert body["total"] == 3
        assert [c["key"] for c in body["crops"]] == sorted(keys)
        for crop in body["crops"]:
            url = urlparse(crop["url"])
            assert f"{url.scheme}://{url.netloc}" == settings.FILESYSTEM_PUBLIC_URL
            assert url.path == f"/{settings.BUCKET_NAME}/{crop['key']}"
            assert "X-Amz-Signature=" in url.query

    def test_pagination(self, client, video, results, phase):
        for n in range(5):
            results(f"{phase}/crop_{n}.jpg")

        body = client.get(f"/videos/{video.id}/{phase}/crops", params={"offset": 3, "limit": 10}).json()

        assert [c["key"].rsplit("/", 1)[1] for c in body["crops"]] == ["crop_3.jpg", "crop_4.jpg"]
        assert (body["total"], body["offset"], body["limit"]) == (5, 3, 10)

    def test_limit_is_capped_at_50(self, client, video, phase):
        assert client.get(f"/videos/{video.id}/{phase}/crops", params={"limit": 500}).json()["limit"] == 50

    def test_empty_when_not_processed(self, client, video, phase):
        body = client.get(f"/videos/{video.id}/{phase}/crops").json()

        assert (body["crops"], body["total"]) == ([], 0)

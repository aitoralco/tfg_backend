import pytest
from fastapi import HTTPException

from app.services.video_service import _parse_range

SIZE = 1000


@pytest.mark.parametrize(
    "header, expected",
    [
        pytest.param(None, (0, 999), id="no-header-is-whole-file"),
        pytest.param("bytes=0-99", (0, 99), id="closed-range"),
        pytest.param("bytes=0-0", (0, 0), id="single-byte"),
        pytest.param("bytes=500-", (500, 999), id="open-ended"),
        pytest.param("bytes=999-999", (999, 999), id="last-byte"),
        pytest.param("bytes=-100", (900, 999), id="suffix"),
        pytest.param("bytes=-5000", (0, 999), id="suffix-longer-than-file"),
    ],
)
def test_valid_ranges(header, expected):
    assert _parse_range(header, SIZE) == expected


@pytest.mark.parametrize("header", ["items=0-10", "garbage", "0-10"])
def test_malformed_header_is_400(header):
    with pytest.raises(HTTPException) as exc:
        _parse_range(header, SIZE)

    assert exc.value.status_code == 400


@pytest.mark.parametrize(
    "header",
    [
        pytest.param("bytes=1000-", id="start-at-eof"),
        pytest.param("bytes=2000-3000", id="start-past-eof"),
        pytest.param("bytes=500-100", id="start-after-end"),
    ],
)
def test_unsatisfiable_range_is_416(header):
    with pytest.raises(HTTPException) as exc:
        _parse_range(header, SIZE)

    assert exc.value.status_code == 416


@pytest.mark.xfail(reason="RFC 9110 section 14.1.2: a last-byte-pos past the end must be clamped, not rejected with 416")
def test_end_past_eof_is_clamped():
    assert _parse_range("bytes=0-5000", SIZE) == (0, 999)

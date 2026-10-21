"""
Shared fixtures for the whole test suite.

Every external service is replaced so the tests never touch real infrastructure:
- Postgres -> in-memory SQLite (fresh schema per test, foreign keys enforced)
- MinIO    -> moto's in-memory S3
- Redis    -> fakeredis (the RQ queue is real, only the server is fake)
- ffmpeg   -> a fake that writes a tiny JPEG
"""

import os

# Settings() is built at import time, so the environment has to be ready before
# anything under `app` is imported. Values here override the developer's .env.
TEST_ENV = {
    "ADMIN_PASSWORD": "admin-password",
    "POSTGRES_USER": "test",
    "POSTGRES_PASSWORD": "test",
    "POSTGRES_SERVER": "localhost",
    "POSTGRES_PORT": "5432",
    "POSTGRES_DB": "test",
    "DEBUG": "false",
    "REDIS_HOST": "localhost",
    "REDIS_PORT": "6379",
    "REDIS_DB": "0",
    "REDIS_PASSWORD": "test",
    "JWT_SECRET_KEY": "test-secret-key-that-is-long-enough-for-hs256",
    "FILESYSTEM_URL": "http://minio.test:9000",
    "FILESYSTEM_PUBLIC_URL": "http://public.minio.test",
    "FILESYSTEM_ACCESS_KEY": "test",
    "FILESYSTEM_ID_KEY": "test",
    "FORCE_PATH_STYLE": "true",
    "REGION_NAME": "us-east-1",
    "BUCKET_NAME": "test-bucket",
    # moto only intercepts AWS endpoints unless told about custom ones
    "MOTO_S3_CUSTOM_ENDPOINTS": "http://minio.test:9000,http://public.minio.test",
    "AWS_ACCESS_KEY_ID": "test",
    "AWS_SECRET_ACCESS_KEY": "test",
}
os.environ.update(TEST_ENV)

from datetime import datetime  # noqa: E402
from types import SimpleNamespace  # noqa: E402

import boto3  # noqa: E402
import fakeredis  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from moto import mock_aws  # noqa: E402
from rq import Queue  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.cache_redis import redis_engine  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.db.session import Base, get_db  # noqa: E402
from app.db.starter import ROLES, VIDEO_STATUS  # noqa: E402
from app.main import app  # noqa: E402
from app.models import RoleModel, UserModel, VideoModel, VideoStatusModel  # noqa: E402
from app.services import user_service, video_service  # noqa: E402
from support import DEFAULT_PASSWORD, FAKE_JPEG  # noqa: E402


def pytest_collection_modifyitems(items):
    """Mark tests by folder so `pytest -m unit` / `-m integration` work without decorators."""
    for item in items:
        path = item.path.as_posix()
        if "/tests/unit/" in path:
            item.add_marker(pytest.mark.unit)
        elif "/tests/integration/" in path:
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session", autouse=True)
def fast_password_hashing():
    """bcrypt's default cost makes each hash ~250ms; the minimum cost keeps the suite fast."""
    user_service.pwd_context.update(bcrypt__rounds=4)


# --- Database ---

@pytest.fixture
def engine():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session_factory(engine):
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    # Same seed data as app/db/starter.py: the services rely on its ids
    # (role_id=2 is "user", status_id=2 is "unprocessed").
    with factory() as seed:
        seed.add_all(RoleModel(name=name) for name in ROLES)
        seed.add_all(VideoStatusModel(status_name=name) for name in VIDEO_STATUS)
        seed.commit()
    return factory


@pytest.fixture
def db(session_factory):
    """Session for arranging and asserting; the API uses its own sessions, like in production."""
    with session_factory() as session:
        yield session


# --- External services ---

@pytest.fixture(scope="session")
def _mocked_aws():
    # Starting moto is slow, so it is started once and emptied after every test
    with mock_aws():
        yield boto3.client("s3", endpoint_url=settings.FILESYSTEM_URL, region_name=settings.REGION_NAME)


@pytest.fixture(autouse=True)
def s3(_mocked_aws):
    """In-memory S3 for every test, so nothing can reach a real MinIO."""
    _mocked_aws.create_bucket(Bucket=settings.BUCKET_NAME)
    yield _mocked_aws
    for bucket in _mocked_aws.list_buckets()["Buckets"]:
        for page in _mocked_aws.get_paginator("list_objects_v2").paginate(Bucket=bucket["Name"]):
            for obj in page.get("Contents", []):
                _mocked_aws.delete_object(Bucket=bucket["Name"], Key=obj["Key"])
        _mocked_aws.delete_bucket(Bucket=bucket["Name"])


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    """RedisEngine talks to an in-memory Redis; tests inspect the RQ queue through it."""
    server = fakeredis.FakeRedis()
    monkeypatch.setattr(redis_engine, "redis", SimpleNamespace(Redis=lambda **_: server))
    return server


class Storage:
    """Small helper over the fake bucket to arrange objects and assert on them."""

    def __init__(self, client):
        self.client = client

    def put(self, key, body):
        self.client.put_object(Bucket=settings.BUCKET_NAME, Key=key, Body=body)

    def get(self, key):
        return self.client.get_object(Bucket=settings.BUCKET_NAME, Key=key)["Body"].read()

    def keys(self, prefix=""):
        response = self.client.list_objects_v2(Bucket=settings.BUCKET_NAME, Prefix=prefix)
        return sorted(obj["Key"] for obj in response.get("Contents", []))


@pytest.fixture
def storage(s3):
    return Storage(s3)


@pytest.fixture
def job_queue(fake_redis):
    return Queue(connection=fake_redis)


@pytest.fixture(autouse=True)
def ffmpeg(monkeypatch):
    """Fake ffmpeg that writes a JPEG to the output path. Set `.returncode` to simulate failures."""
    fake = SimpleNamespace(returncode=0, calls=[])

    def run(cmd, **_):
        fake.calls.append(cmd)
        if fake.returncode == 0:
            with open(cmd[-1], "wb") as f:
                f.write(FAKE_JPEG)
        return SimpleNamespace(returncode=fake.returncode, stderr=b"fake ffmpeg error")

    monkeypatch.setattr(video_service.subprocess, "run", run)
    return fake


# --- HTTP client ---

@pytest.fixture
def client(session_factory):
    def override_get_db():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def client_no_raise(client):
    """Client that returns 500 responses instead of re-raising server errors."""
    return TestClient(app, raise_server_exceptions=False)


# --- Factories ---

@pytest.fixture
def make_user(db):
    counter = iter(range(1, 10_000))

    def _make_user(username=None, email=None, password=DEFAULT_PASSWORD, role="user"):
        n = next(counter)
        role_model = db.query(RoleModel).filter_by(name=role).one()
        user = UserModel(
            username=username or f"user{n}",
            email=email or f"user{n}@example.com",
            password_hash=user_service.get_password_hash(password),
            role_id=role_model.id,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    return _make_user


@pytest.fixture
def user(make_user):
    return make_user(username="alice", email="alice@example.com")


@pytest.fixture
def other_user(make_user):
    return make_user(username="bob", email="bob@example.com")


@pytest.fixture
def admin(make_user):
    return make_user(username="root", email="root@example.com", role="admin")


@pytest.fixture
def auth_headers():
    def _auth_headers(user):
        return {"Authorization": f"Bearer {create_access_token(user.id, user.role.name)}"}

    return _auth_headers


@pytest.fixture
def make_video(db, storage):
    """
    Create a video row. With `content`, also stores the file (and a thumbnail) in S3
    under the same keys the backend uses: {user_id}/{group_id}/{file_name}.
    """
    counter = iter(range(1, 10_000))

    def _make_video(
        owner,
        title=None,
        description=None,
        shared=True,
        status="unprocessed",
        created_at=None,
        content=None,
        thumbnail=None,
    ):
        n = next(counter)
        status_model = db.query(VideoStatusModel).filter_by(status_name=status).one()
        video = VideoModel(
            user_id=owner.id,
            title=title or f"video {n}",
            description=description,
            file_name=f"file{n}.mp4",
            shared=shared,
            status_id=status_model.id,
            created_at=created_at or datetime(2026, 1, 1, 12, 0, n % 60),
        )
        db.add(video)
        db.flush()
        video.group_id = video.id
        db.commit()
        db.refresh(video)
        if content is not None:
            storage.put(f"{owner.id}/{video.group_id}/{video.file_name}", content)
        if thumbnail is not None:
            storage.put(f"{owner.id}/{video.group_id}/thumbnail.jpg", thumbnail)
        return video

    return _make_video

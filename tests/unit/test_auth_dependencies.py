from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt

from app.core.auth import get_current_admin, get_current_user, get_optional_user
from app.core.config import settings
from app.core.security import ALGORITHM, create_access_token


def bearer(token):
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def token_for(user):
    return create_access_token(user.id, user.role.name)


def signed(payload):
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=ALGORITHM)


class TestGetCurrentUser:
    def test_returns_the_token_owner(self, db, user):
        assert get_current_user(bearer(token_for(user)), db).id == user.id

    @pytest.mark.parametrize(
        "token",
        [
            pytest.param("garbage", id="malformed"),
            pytest.param(signed({"role": "user"}), id="without-sub"),
            pytest.param(signed({"sub": "abc"}), id="non-numeric-sub"),
            pytest.param(
                signed({"sub": "1", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)}),
                id="expired",
            ),
        ],
    )
    def test_invalid_token_is_401(self, db, user, token):
        with pytest.raises(HTTPException) as exc:
            get_current_user(bearer(token), db)

        assert exc.value.status_code == 401
        assert exc.value.detail == "Invalid or expired token"

    def test_token_of_deleted_user_is_401(self, db, user):
        token = token_for(user)
        db.delete(user)
        db.commit()

        with pytest.raises(HTTPException) as exc:
            get_current_user(bearer(token), db)

        assert exc.value.status_code == 401
        assert exc.value.detail == "User not found"


class TestGetOptionalUser:
    def test_no_token_means_anonymous(self, db):
        assert get_optional_user(credentials=None, token=None, db=db) is None

    def test_reads_token_from_header(self, db, user):
        assert get_optional_user(bearer(token_for(user)), token=None, db=db).id == user.id

    def test_reads_token_from_query_string(self, db, user):
        # <video src="...?token="> cannot send an Authorization header
        assert get_optional_user(credentials=None, token=token_for(user), db=db).id == user.id

    def test_header_wins_over_query_string(self, db, user, other_user):
        result = get_optional_user(bearer(token_for(user)), token=token_for(other_user), db=db)

        assert result.id == user.id

    def test_invalid_token_means_anonymous_instead_of_error(self, db):
        assert get_optional_user(bearer("garbage"), token=None, db=db) is None


class TestGetCurrentAdmin:
    def test_admin_passes(self, admin):
        assert get_current_admin(admin) is admin

    def test_regular_user_is_403(self, user):
        with pytest.raises(HTTPException) as exc:
            get_current_admin(user)

        assert exc.value.status_code == 403

from datetime import datetime, timedelta, timezone

import pytest
from jose import ExpiredSignatureError, JWTError, jwt

from app.core.config import settings
from app.core.security import ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, create_access_token, decode_token
from app.services.user_service import get_password_hash, pwd_context, verify_password


class TestAccessToken:
    def test_round_trip_keeps_user_id_and_role(self):
        payload = decode_token(create_access_token(user_id=42, role="admin"))

        assert payload["sub"] == "42"
        assert payload["role"] == "admin"

    def test_expires_after_configured_lifetime(self):
        before = datetime.now(timezone.utc)
        payload = decode_token(create_access_token(user_id=1, role="user"))

        expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        expected = before + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        assert abs(expires_at - expected) < timedelta(seconds=5)

    def test_expired_token_is_rejected(self):
        expired = jwt.encode(
            {"sub": "1", "role": "user", "exp": datetime.now(timezone.utc) - timedelta(seconds=1)},
            settings.JWT_SECRET_KEY,
            algorithm=ALGORITHM,
        )

        with pytest.raises(ExpiredSignatureError):
            decode_token(expired)

    def test_token_signed_with_another_key_is_rejected(self):
        forged = jwt.encode({"sub": "1", "role": "admin"}, "not-the-server-key", algorithm=ALGORITHM)

        with pytest.raises(JWTError):
            decode_token(forged)

    def test_token_with_another_algorithm_is_rejected(self):
        token = jwt.encode({"sub": "1", "role": "admin"}, settings.JWT_SECRET_KEY, algorithm="HS512")

        with pytest.raises(JWTError):
            decode_token(token)

    def test_tampered_payload_is_rejected(self):
        header, _, signature = create_access_token(user_id=1, role="user").split(".")
        admin_payload = jwt.encode({"sub": "1", "role": "admin"}, "x", algorithm=ALGORITHM).split(".")[1]

        with pytest.raises(JWTError):
            decode_token(f"{header}.{admin_payload}.{signature}")

    @pytest.mark.parametrize("garbage", ["", "not-a-jwt", "a.b.c"])
    def test_malformed_token_is_rejected(self, garbage):
        with pytest.raises(JWTError):
            decode_token(garbage)


class TestPasswordHashing:
    def test_hash_is_bcrypt_and_not_the_plain_password(self):
        hashed = get_password_hash("hunter2")

        assert hashed != "hunter2"
        assert pwd_context.identify(hashed) == "bcrypt"

    def test_same_password_gets_different_salts(self):
        assert get_password_hash("hunter2") != get_password_hash("hunter2")

    def test_verify_accepts_right_password(self):
        assert verify_password("hunter2", get_password_hash("hunter2"))

    @pytest.mark.parametrize("attempt", ["hunter3", "Hunter2", "", "hunter2 "])
    def test_verify_rejects_wrong_password(self, attempt):
        assert not verify_password(attempt, get_password_hash("hunter2"))

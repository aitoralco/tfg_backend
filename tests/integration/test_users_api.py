import pytest

from app.core.security import decode_token
from app.models import UserModel
from app.services.user_service import verify_password
from support import DEFAULT_PASSWORD

# FastAPI's HTTPBearer answers 403 (not 401) when the Authorization header is missing
NO_CREDENTIALS = 403


def login(client, username, password=DEFAULT_PASSWORD):
    return client.post("/users/login", json={"username": username, "password": password})


class TestRegister:
    def test_creates_a_regular_user(self, client, db):
        response = client.post(
            "/users/register",
            json={"username": "carol", "email": "carol@example.com", "password": "pw-123456"},
        )

        assert response.status_code == 201
        body = response.json()
        assert body["username"] == "carol"
        assert body["email"] == "carol@example.com"
        assert body["role"]["name"] == "user"
        assert "password" not in body and "password_hash" not in body

        stored = db.get(UserModel, body["id"])
        assert stored.password_hash != "pw-123456"
        assert verify_password("pw-123456", stored.password_hash)

    def test_cannot_self_register_as_admin(self, client):
        response = client.post(
            "/users/register",
            json={
                "username": "mallory",
                "email": "mallory@example.com",
                "password": "pw",
                "role_id": 1,
                "role": {"id": 1, "name": "admin"},
            },
        )

        assert response.status_code == 201
        assert response.json()["role"]["name"] == "user"

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param({"username": "x", "email": "not-an-email", "password": "pw"}, id="bad-email"),
            pytest.param({"username": "x", "email": "x@example.com"}, id="no-password"),
            pytest.param({"email": "x@example.com", "password": "pw"}, id="no-username"),
        ],
    )
    def test_invalid_payload_is_422(self, client, payload):
        assert client.post("/users/register", json=payload).status_code == 422

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param({"username": "alice", "email": "new@example.com", "password": "pw"}, id="username"),
            pytest.param({"username": "new", "email": "alice@example.com", "password": "pw"}, id="email"),
        ],
    )
    def test_duplicate_is_a_client_error(self, client_no_raise, user, payload):
        response = client_no_raise.post("/users/register", json=payload)

        assert response.status_code in (400, 409)


class TestLogin:
    def test_returns_a_token_for_the_user(self, client, user):
        response = login(client, "alice")

        assert response.status_code == 200
        body = response.json()
        assert body["token_type"] == "bearer"
        assert body["user"]["id"] == user.id
        payload = decode_token(body["access_token"])
        assert payload["sub"] == str(user.id)
        assert payload["role"] == "user"

    def test_token_carries_admin_role(self, client, admin):
        token = login(client, admin.username).json()["access_token"]

        assert decode_token(token)["role"] == "admin"

    def test_token_from_login_authenticates(self, client, user):
        token = login(client, "alice").json()["access_token"]

        response = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})

        assert response.json()["id"] == user.id

    @pytest.mark.parametrize(
        "username, password",
        [
            pytest.param("alice", "wrong-password", id="wrong-password"),
            pytest.param("nobody", DEFAULT_PASSWORD, id="unknown-user"),
        ],
    )
    def test_bad_credentials_are_401_without_saying_which_part_failed(self, client, user, username, password):
        response = login(client, username, password)

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid credentials"


class TestMe:
    def test_returns_current_user(self, client, user, auth_headers):
        response = client.get("/users/me", headers=auth_headers(user))

        assert response.status_code == 200
        assert response.json()["username"] == "alice"

    def test_requires_credentials(self, client):
        assert client.get("/users/me").status_code == NO_CREDENTIALS

    def test_invalid_token_is_401(self, client):
        response = client.get("/users/me", headers={"Authorization": "Bearer garbage"})

        assert response.status_code == 401


class TestUpdateMe:
    def test_updates_username_and_email_keeping_id(self, client, db, user, auth_headers):
        response = client.patch(
            "/users/me",
            headers=auth_headers(user),
            json={"current_password": DEFAULT_PASSWORD, "username": "alice2", "email": "alice2@example.com"},
        )

        assert response.status_code == 200
        assert response.json()["id"] == user.id
        db.refresh(user)
        assert (user.username, user.email) == ("alice2", "alice2@example.com")

    def test_omitted_fields_are_left_untouched(self, client, db, user, auth_headers):
        client.patch(
            "/users/me",
            headers=auth_headers(user),
            json={"current_password": DEFAULT_PASSWORD, "username": "alice2"},
        )

        db.refresh(user)
        assert user.email == "alice@example.com"

    def test_password_change_replaces_the_old_one(self, client, user, auth_headers):
        response = client.patch(
            "/users/me",
            headers=auth_headers(user),
            json={"current_password": DEFAULT_PASSWORD, "new_password": "brand-new-pw"},
        )

        assert response.status_code == 200
        assert login(client, "alice", DEFAULT_PASSWORD).status_code == 401
        assert login(client, "alice", "brand-new-pw").status_code == 200

    def test_wrong_current_password_is_403_and_changes_nothing(self, client, db, user, auth_headers):
        response = client.patch(
            "/users/me",
            headers=auth_headers(user),
            json={"current_password": "wrong", "username": "hacked", "new_password": "hacked"},
        )

        assert response.status_code == 403
        db.refresh(user)
        assert user.username == "alice"
        assert verify_password(DEFAULT_PASSWORD, user.password_hash)

    def test_current_password_is_mandatory(self, client, user, auth_headers):
        response = client.patch("/users/me", headers=auth_headers(user), json={"username": "x"})

        assert response.status_code == 422

    def test_cannot_promote_itself(self, client, db, user, auth_headers):
        client.patch(
            "/users/me",
            headers=auth_headers(user),
            json={"current_password": DEFAULT_PASSWORD, "role_id": 1},
        )

        db.refresh(user)
        assert user.role.name == "user"

    def test_taking_another_users_username_is_a_client_error(
        self, client_no_raise, user, other_user, auth_headers
    ):
        response = client_no_raise.patch(
            "/users/me",
            headers=auth_headers(user),
            json={"current_password": DEFAULT_PASSWORD, "username": other_user.username},
        )

        assert response.status_code in (400, 409)


class TestDeleteMe:
    def test_deletes_the_account(self, client, db, user, auth_headers):
        response = client.request(
            "DELETE", "/users/me", headers=auth_headers(user), json={"current_password": DEFAULT_PASSWORD}
        )

        assert response.status_code == 204
        assert db.query(UserModel).filter_by(id=user.id).one_or_none() is None
        assert login(client, "alice").status_code == 401

    def test_wrong_password_is_403_and_keeps_the_account(self, client, db, user, auth_headers):
        response = client.request(
            "DELETE", "/users/me", headers=auth_headers(user), json={"current_password": "wrong"}
        )

        assert response.status_code == 403
        assert db.query(UserModel).filter_by(id=user.id).one_or_none() is not None

    def test_token_is_useless_after_deletion(self, client, user, auth_headers):
        headers = auth_headers(user)
        client.request("DELETE", "/users/me", headers=headers, json={"current_password": DEFAULT_PASSWORD})

        assert client.get("/users/me", headers=headers).status_code == 401

    @pytest.mark.xfail(reason="Users with videos cannot be deleted: videos.user_id is set to NULL and the DB rejects it (500)")
    def test_user_with_videos_can_delete_the_account(self, client_no_raise, user, make_video, auth_headers):
        make_video(user)

        response = client_no_raise.request(
            "DELETE", "/users/me", headers=auth_headers(user), json={"current_password": DEFAULT_PASSWORD}
        )

        assert response.status_code == 204


class TestReadUser:
    def test_any_logged_user_can_read_a_user(self, client, user, other_user, auth_headers):
        response = client.get(f"/users/{other_user.id}", headers=auth_headers(user))

        assert response.status_code == 200
        assert response.json()["username"] == "bob"

    def test_unknown_user_is_404(self, client, user, auth_headers):
        assert client.get("/users/9999", headers=auth_headers(user)).status_code == 404

    def test_requires_credentials(self, client, user):
        assert client.get(f"/users/{user.id}").status_code == NO_CREDENTIALS


class TestAdminEndpoints:
    def test_admin_lists_every_user(self, client, admin, user, other_user, auth_headers):
        response = client.get("/users/all", headers=auth_headers(admin))

        assert response.status_code == 200
        assert {u["username"] for u in response.json()} == {"root", "alice", "bob"}

    @pytest.mark.parametrize(
        "method, path, payload",
        [
            ("GET", "/users/all", None),
            ("PUT", "/users/{id}", {"username": "x"}),
            ("DELETE", "/users/{id}", None),
            ("POST", "/users/roles", {"name": "moderator", "role_id": 10}),
        ],
    )
    def test_regular_users_are_forbidden(self, client, user, other_user, auth_headers, method, path, payload):
        response = client.request(
            method, path.format(id=other_user.id), headers=auth_headers(user), json=payload
        )

        assert response.status_code == 403

    def test_admin_updates_any_field_except_id(self, client, db, admin, user, auth_headers):
        response = client.put(
            f"/users/{user.id}",
            headers=auth_headers(admin),
            json={"username": "renamed", "email": "renamed@example.com", "password": "reset-pw", "role_id": 1},
        )

        assert response.status_code == 200
        assert response.json()["id"] == user.id
        db.refresh(user)
        assert (user.username, user.email, user.role.name) == ("renamed", "renamed@example.com", "admin")
        assert verify_password("reset-pw", user.password_hash)

    def test_admin_does_not_need_the_users_password(self, client, admin, user, auth_headers):
        response = client.put(f"/users/{user.id}", headers=auth_headers(admin), json={"username": "xyz"})

        assert response.status_code == 200

    def test_admin_can_update_another_admin(self, client, db, make_user, admin, auth_headers):
        other_admin = make_user(role="admin")

        response = client.put(f"/users/{other_admin.id}", headers=auth_headers(admin), json={"role_id": 2})

        assert response.status_code == 200
        db.refresh(other_admin)
        assert other_admin.role.name == "user"

    def test_admin_update_of_unknown_user_is_404(self, client, admin, auth_headers):
        assert client.put("/users/9999", headers=auth_headers(admin), json={"username": "xyz"}).status_code == 404

    def test_admin_deletes_a_user(self, client, db, admin, user, auth_headers):
        response = client.delete(f"/users/{user.id}", headers=auth_headers(admin))

        assert response.status_code == 204
        assert db.query(UserModel).filter_by(id=user.id).one_or_none() is None

    def test_admin_delete_of_unknown_user_is_404(self, client, admin, auth_headers):
        assert client.delete("/users/9999", headers=auth_headers(admin)).status_code == 404

    def test_demoted_admin_loses_access_with_the_same_token(self, client, make_user, admin, auth_headers):
        other_admin = make_user(role="admin")
        headers = auth_headers(other_admin)
        client.put(f"/users/{other_admin.id}", headers=auth_headers(admin), json={"role_id": 2})

        # The role is read from the DB on each request, not trusted from the token
        assert client.get("/users/all", headers=headers).status_code == 403

    def test_admin_creates_a_role(self, client, admin, auth_headers):
        response = client.post("/users/roles", headers=auth_headers(admin), json={"name": "moderator", "role_id": 10})

        assert response.status_code == 200
        assert response.json() == {"id": 10, "name": "moderator"}

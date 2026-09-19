def test_application_starts(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200


def test_auth_health_endpoint(client) -> None:
    response = client.get("/api/v1/auth/health")
    assert response.status_code == 200
    assert response.json() == {"message": "Auth service is running"}


def test_register_login_and_current_user(client) -> None:
    registration = client.post(
        "/api/v1/auth/register",
        json={"name": "Dixit", "email": "dixit@example.com", "password": "password123"},
    )
    assert registration.status_code == 201
    assert registration.json()["email"] == "dixit@example.com"
    assert "password_hash" not in registration.json()

    login = client.post(
        "/api/v1/auth/login",
        data={"username": "dixit@example.com", "password": "password123"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    current_user = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert current_user.status_code == 200
    assert current_user.json() == {
        "id": registration.json()["id"],
        "name": "Dixit",
        "email": "dixit@example.com",
    }


def test_duplicate_registration_is_rejected(client) -> None:
    payload = {"name": "Dixit", "email": "dixit@example.com", "password": "password123"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    assert client.post("/api/v1/auth/register", json=payload).status_code == 409

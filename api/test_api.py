from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from main import create_app


PASSWORD = "StrongPass-12@"


@pytest.fixture
def client(tmp_path):
    application = create_app(tmp_path / "taskflow-test.sqlite3")
    with TestClient(application) as test_client:
        yield test_client


def register(client: TestClient, username: str = "qa_tester") -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": PASSWORD},
    )
    assert response.status_code == 201


def login(client: TestClient, username: str = "qa_tester") -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": PASSWORD},
    )
    assert response.status_code == 200
    return response.json()["accessToken"]


def test_register_normalizes_username_and_rejects_duplicate(client: TestClient):
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "QA_Tester", "password": PASSWORD},
    )

    assert response.status_code == 201
    assert response.json()["username"] == "qa_tester"
    assert "password" not in response.json()
    assert "password_hash" not in response.json()

    duplicate = client.post(
        "/api/v1/auth/register",
        json={"username": "Qa_Tester", "password": PASSWORD},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "CONFLICT"


def test_registration_rejects_invalid_username_and_password(client: TestClient):
    invalid_username = client.post(
        "/api/v1/auth/register",
        json={"username": "bad@name", "password": PASSWORD},
    )
    assert invalid_username.status_code == 400
    assert invalid_username.json()["error"]["code"] == "VALIDATION_ERROR"

    invalid_password = client.post(
        "/api/v1/auth/register",
        json={"username": "qa_tester", "password": "lettersOnly"},
    )
    assert invalid_password.status_code == 400
    assert invalid_password.json()["error"]["code"] == "VALIDATION_ERROR"


def test_login_logout_and_protected_routes(client: TestClient):
    register(client)
    assert client.get("/api/v1/tasks").status_code == 401

    invalid_login = client.post(
        "/api/v1/auth/login",
        json={"username": "qa_tester", "password": "WrongPass-12@"},
    )
    assert invalid_login.status_code == 401
    assert invalid_login.json()["error"]["code"] == "UNAUTHORIZED"

    token = login(client)
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/tasks", headers=headers).status_code == 200

    logout = client.post("/api/v1/auth/logout", headers=headers)
    assert logout.status_code == 204
    assert logout.content == b""
    assert client.get("/api/v1/tasks", headers=headers).status_code == 401


def test_task_crud_filters_and_dashboard_summary(client: TestClient):
    register(client)
    headers = {"Authorization": f"Bearer {login(client)}"}
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    in_progress = client.post(
        "/api/v1/tasks",
        headers=headers,
        json={
            "title": "API smoke tests",
            "description": "Check task endpoints",
            "status": "in-progress",
            "priority": "high",
            "dueDate": yesterday,
        },
    )
    assert in_progress.status_code == 201
    task = in_progress.json()
    assert task["title"] == "API smoke tests"
    assert task["dueDate"] == yesterday
    assert task["createdAt"] == task["updatedAt"]

    completed = client.post(
        "/api/v1/tasks",
        headers=headers,
        json={"title": "Write API notes", "status": "completed", "dueDate": yesterday},
    )
    assert completed.status_code == 201
    assert completed.json()["priority"] == "medium"

    filtered = client.get(
        "/api/v1/tasks",
        headers=headers,
        params={"q": "SMOKE", "status": "in-progress"},
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["id"] == task["id"]

    summary = client.get("/api/v1/dashboard/summary", headers=headers)
    assert summary.json() == {
        "total": 2,
        "inProgress": 1,
        "completed": 1,
        "overdue": 1,
    }

    updated = client.patch(
        f"/api/v1/tasks/{task['id']}",
        headers=headers,
        json={"title": "API tests reviewed", "status": "completed"},
    )
    assert updated.status_code == 200
    assert updated.json()["createdAt"] == task["createdAt"]
    assert updated.json()["updatedAt"] > task["updatedAt"]

    summary_after_update = client.get(
        "/api/v1/dashboard/summary", headers=headers
    ).json()
    assert summary_after_update == {
        "total": 2,
        "inProgress": 0,
        "completed": 2,
        "overdue": 0,
    }

    deleted = client.delete(f"/api/v1/tasks/{task['id']}", headers=headers)
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert client.get(f"/api/v1/tasks/{task['id']}", headers=headers).status_code == 404


def test_users_cannot_access_another_users_tasks(client: TestClient):
    register(client, "qa_first")
    first_headers = {"Authorization": f"Bearer {login(client, 'qa_first')}"}
    task = client.post(
        "/api/v1/tasks",
        headers=first_headers,
        json={"title": "Private task"},
    ).json()

    register(client, "qa_second")
    second_headers = {"Authorization": f"Bearer {login(client, 'qa_second')}"}
    assert client.get("/api/v1/tasks", headers=second_headers).json()["total"] == 0
    assert (
        client.get(f"/api/v1/tasks/{task['id']}", headers=second_headers).status_code
        == 404
    )
    assert (
        client.patch(
            f"/api/v1/tasks/{task['id']}",
            headers=second_headers,
            json={"title": "Changed"},
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/api/v1/tasks/{task['id']}", headers=second_headers).status_code
        == 404
    )


def test_invalid_task_and_non_json_requests_return_consistent_errors(
    client: TestClient,
):
    register(client)
    headers = {"Authorization": f"Bearer {login(client)}"}
    invalid_task = client.post(
        "/api/v1/tasks",
        headers=headers,
        json={"title": "   ", "status": "blocked"},
    )
    assert invalid_task.status_code == 400
    assert invalid_task.json()["error"]["code"] == "VALIDATION_ERROR"

    wrong_content_type = client.post(
        "/api/v1/tasks",
        headers={**headers, "Content-Type": "text/plain"},
        content='{"title":"Ignored"}',
    )
    assert wrong_content_type.status_code == 415
    assert wrong_content_type.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"

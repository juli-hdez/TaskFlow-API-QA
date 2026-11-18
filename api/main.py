from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from starlette.exceptions import HTTPException as StarletteHTTPException


API_PREFIX = "/api/v1"
PASSWORD_ITERATIONS = 600_000
TOKEN_LIFETIME = timedelta(hours=8)
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]{3,20}$")
PASSWORD_PATTERN = re.compile(r"^[A-Za-z0-9._@-]+$")
TaskStatus = Literal["pending", "in-progress", "completed"]
TaskPriority = Literal["low", "medium", "high"]


def current_time() -> datetime:
    return datetime.now(timezone.utc)


def timestamp(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def default_database_path() -> Path:
    configured_path = os.environ.get("TASKFLOW_DB_PATH")
    if configured_path:
        return Path(configured_path).expanduser()
    return Path.home() / ".taskflow" / "taskflow.db"


def initialize_database(database_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                username_key TEXT NOT NULL UNIQUE,
                password_salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL,
                priority TEXT NOT NULL,
                due_date TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS tasks_by_user_created
            ON tasks(user_id, created_at DESC);
            """
        )


def get_database(request: Request):
    connection = sqlite3.connect(request.app.state.database_path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
    finally:
        connection.close()


Database = Annotated[sqlite3.Connection, Depends(get_database)]


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str
    password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        normalized = value.strip()
        if not USERNAME_PATTERN.fullmatch(normalized):
            raise ValueError(
                "El nombre de usuario debe tener entre 3 y 20 caracteres válidos."
            )
        return normalized.lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not PASSWORD_PATTERN.fullmatch(value):
            raise ValueError("La contraseña contiene caracteres no permitidos.")
        if (
            sum(character.isascii() and character.isalpha() for character in value) < 8
            or sum(character.isdigit() for character in value) < 2
            or not any(character in "._@-" for character in value)
        ):
            raise ValueError("La contraseña no cumple con los parámetros solicitados.")
        return value


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip().lower()


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    title: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    status: TaskStatus = "pending"
    priority: TaskPriority = "medium"
    due_date: date | None = Field(default=None, alias="dueDate")

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("El título no puede estar vacío.")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    title: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    due_date: date | None = Field(default=None, alias="dueDate")

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("El título no puede estar vacío.")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def validate_patch(self) -> TaskUpdate:
        if not self.model_fields_set:
            raise ValueError("Indica al menos un campo para actualizar.")
        for field_name in ("title", "status", "priority"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"El campo {field_name} no puede ser nulo.")
        return self


@dataclass(frozen=True)
class AuthenticatedUser:
    id: str
    username: str
    token_hash: str


def hash_password(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS
    )


def serialize_task(row: sqlite3.Row) -> dict[str, object]:
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "status": row["status"],
        "priority": row["priority"],
        "dueDate": row["due_date"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    connection: sqlite3.Connection = Depends(get_database),
) -> AuthenticatedUser:
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Se requiere autenticación.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    scheme, separator, token = authorization.partition(" ")
    if not separator or scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=401,
            detail="El token de autenticación no es válido.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_hash = hashlib.sha256(token.strip().encode("utf-8")).hexdigest()
    session = connection.execute(
        """
        SELECT users.id, users.username, sessions.expires_at
        FROM sessions
        JOIN users ON users.id = sessions.user_id
        WHERE sessions.token_hash = ?
        """,
        (token_hash,),
    ).fetchone()

    if session is None:
        raise HTTPException(
            status_code=401,
            detail="El token de autenticación no es válido.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if session["expires_at"] <= timestamp(current_time()):
        connection.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
        connection.commit()
        raise HTTPException(
            status_code=401,
            detail="El token de autenticación ha expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return AuthenticatedUser(
        id=session["id"],
        username=session["username"],
        token_hash=token_hash,
    )


CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


def create_app(database_path: str | Path | None = None) -> FastAPI:
    resolved_database_path = Path(database_path) if database_path else default_database_path()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        initialize_database(application.state.database_path)
        yield

    application = FastAPI(
        title="Taskflow API",
        description="API local para registro, tareas y resumen de Taskflow.",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.state.database_path = resolved_database_path

    @application.middleware("http")
    async def require_json_for_body_requests(request: Request, call_next):
        path = request.url.path
        has_json_body_route = (
            path
            in {
                f"{API_PREFIX}/auth/register",
                f"{API_PREFIX}/auth/login",
                f"{API_PREFIX}/tasks",
            }
            or (request.method == "PATCH" and path.startswith(f"{API_PREFIX}/tasks/"))
        )
        if request.method in {"POST", "PATCH"} and has_json_body_route:
            content_type = request.headers.get("content-type", "").split(";", 1)[0]
            if content_type.strip().lower() != "application/json":
                return JSONResponse(
                    status_code=415,
                    content={
                        "error": {
                            "code": "UNSUPPORTED_MEDIA_TYPE",
                            "message": "El tipo de contenido debe ser application/json.",
                        }
                    },
                )
        return await call_next(request)

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exception: RequestValidationError
    ) -> JSONResponse:
        details = [
            {
                "field": ".".join(str(part) for part in error["loc"]),
                "message": error["msg"],
            }
            for error in exception.errors()
        ]
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "La solicitud no es válida.",
                    "details": details,
                }
            },
        )

    @application.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exception: StarletteHTTPException
    ) -> JSONResponse:
        error_codes = {
            400: "VALIDATION_ERROR",
            401: "UNAUTHORIZED",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            409: "CONFLICT",
            415: "UNSUPPORTED_MEDIA_TYPE",
        }
        return JSONResponse(
            status_code=exception.status_code,
            content={
                "error": {
                    "code": error_codes.get(exception.status_code, "HTTP_ERROR"),
                    "message": str(exception.detail),
                }
            },
            headers=exception.headers,
        )

    router = APIRouter(prefix=API_PREFIX)

    @router.post("/auth/register", status_code=201)
    def register(payload: RegisterRequest, connection: Database):
        username = payload.username
        salt = secrets.token_bytes(16)
        password_hash = hash_password(payload.password, salt)
        user_id = str(uuid.uuid4())

        try:
            connection.execute(
                """
                INSERT INTO users (id, username, username_key, password_salt, password_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    username,
                    username,
                    salt.hex(),
                    password_hash.hex(),
                    timestamp(current_time()),
                ),
            )
            connection.commit()
        except sqlite3.IntegrityError:
            connection.rollback()
            raise HTTPException(
                status_code=409,
                detail="Este nombre de usuario ya está en uso.",
            ) from None

        return {"id": user_id, "username": username}

    @router.post("/auth/login")
    def login(payload: LoginRequest, connection: Database):
        username = payload.username
        user = connection.execute(
            "SELECT id, username, password_salt, password_hash FROM users WHERE username_key = ?",
            (username,),
        ).fetchone()

        salt = bytes.fromhex(user["password_salt"]) if user else bytes(16)
        candidate_hash = hash_password(payload.password, salt)
        password_matches = hmac.compare_digest(
            candidate_hash.hex(), user["password_hash"] if user else bytes(32).hex()
        )
        if user is None or not password_matches:
            raise HTTPException(
                status_code=401,
                detail="Nombre de usuario o contraseña incorrectos.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = secrets.token_urlsafe(32)
        expires_at = current_time() + TOKEN_LIFETIME
        connection.execute(
            "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
            (
                hashlib.sha256(token.encode("utf-8")).hexdigest(),
                user["id"],
                timestamp(expires_at),
            ),
        )
        connection.commit()
        return {
            "accessToken": token,
            "tokenType": "Bearer",
            "expiresIn": int(TOKEN_LIFETIME.total_seconds()),
        }

    @router.post("/auth/logout", status_code=204)
    def logout(user: CurrentUser, connection: Database) -> Response:
        connection.execute(
            "DELETE FROM sessions WHERE token_hash = ?", (user.token_hash,)
        )
        connection.commit()
        return Response(status_code=204)

    @router.post("/tasks", status_code=201)
    def create_task(payload: TaskCreate, user: CurrentUser, connection: Database):
        now = timestamp(current_time())
        task_id = str(uuid.uuid4())
        connection.execute(
            """
            INSERT INTO tasks (
                id, user_id, title, description, status, priority, due_date, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                user.id,
                payload.title,
                payload.description,
                payload.status,
                payload.priority,
                payload.due_date.isoformat() if payload.due_date else None,
                now,
                now,
            ),
        )
        connection.commit()
        row = connection.execute(
            "SELECT * FROM tasks WHERE id = ? AND user_id = ?", (task_id, user.id)
        ).fetchone()
        return serialize_task(row)

    @router.get("/tasks")
    def list_tasks(
        user: CurrentUser,
        connection: Database,
        q: str | None = None,
        status: TaskStatus | None = None,
    ):
        conditions = ["user_id = ?"]
        parameters: list[object] = [user.id]

        if status is not None:
            conditions.append("status = ?")
            parameters.append(status)
        if q:
            conditions.append("(LOWER(title) LIKE ? OR LOWER(COALESCE(description, '')) LIKE ?)")
            search_term = f"%{q.strip().lower()}%"
            parameters.extend([search_term, search_term])

        rows = connection.execute(
            f"SELECT * FROM tasks WHERE {' AND '.join(conditions)} ORDER BY created_at DESC",
            parameters,
        ).fetchall()
        return {"items": [serialize_task(row) for row in rows], "total": len(rows)}

    def get_owned_task(
        connection: sqlite3.Connection, task_id: str, user_id: str
    ) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="No se encontró la tarea.")
        return row

    @router.get("/tasks/{task_id}")
    def get_task(task_id: str, user: CurrentUser, connection: Database):
        return serialize_task(get_owned_task(connection, task_id, user.id))

    @router.patch("/tasks/{task_id}")
    def update_task(
        task_id: str,
        payload: TaskUpdate,
        user: CurrentUser,
        connection: Database,
    ):
        existing_task = get_owned_task(connection, task_id, user.id)
        changes = payload.model_dump(exclude_unset=True, by_alias=False)
        column_names = {
            "title": "title",
            "description": "description",
            "status": "status",
            "priority": "priority",
            "due_date": "due_date",
        }
        assignments: list[str] = []
        values: list[object] = []
        for field_name, value in changes.items():
            assignments.append(f"{column_names[field_name]} = ?")
            values.append(value.isoformat() if isinstance(value, date) else value)
        previous_update = datetime.fromisoformat(
            existing_task["updated_at"].replace("Z", "+00:00")
        )
        updated_at = current_time()
        if updated_at <= previous_update:
            updated_at = previous_update + timedelta(microseconds=1)
        assignments.append("updated_at = ?")
        values.extend([timestamp(updated_at), task_id, user.id])
        connection.execute(
            f"UPDATE tasks SET {', '.join(assignments)} WHERE id = ? AND user_id = ?",
            values,
        )
        connection.commit()
        return serialize_task(get_owned_task(connection, task_id, user.id))

    @router.delete("/tasks/{task_id}", status_code=204)
    def delete_task(
        task_id: str, user: CurrentUser, connection: Database
    ) -> Response:
        cursor = connection.execute(
            "DELETE FROM tasks WHERE id = ? AND user_id = ?", (task_id, user.id)
        )
        connection.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="No se encontró la tarea.")
        return Response(status_code=204)

    @router.get("/dashboard/summary")
    def dashboard_summary(user: CurrentUser, connection: Database):
        rows = connection.execute(
            "SELECT status, due_date FROM tasks WHERE user_id = ?", (user.id,)
        ).fetchall()
        today = date.today().isoformat()
        return {
            "total": len(rows),
            "inProgress": sum(row["status"] == "in-progress" for row in rows),
            "completed": sum(row["status"] == "completed" for row in rows),
            "overdue": sum(
                row["due_date"] is not None
                and row["due_date"] < today
                and row["status"] != "completed"
                for row in rows
            ),
        }

    application.include_router(router)
    return application


app = create_app()

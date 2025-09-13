# tests/conftest.py
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pytest
import pytest_asyncio
import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.session import Base, get_db
from app.core.security import get_password_hash
from app.models.user import User

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

sync_engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)

# ---------- Fixtures ----------
@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Crea las tablas en SQLite antes de los tests."""
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)

@pytest.fixture()
def db_session():
    """Provee una sesión de DB aislada por test (rollback automático)."""
    connection = sync_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    try:
        yield session
    finally:
        # 🔑 Hacer rollback ANTES de cerrar para evitar SAWarning
        if transaction.is_active:
            transaction.rollback()
        session.close()
        connection.close()

@pytest_asyncio.fixture()
async def client(db_session):
    """Provee un AsyncClient con DB inyectada."""
    def override_get_db():
        # 🔑 No cerrar la sesión acá; la cierra el fixture db_session
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

@pytest.fixture()
def admin_user(db_session):
    """Crea un usuario admin para tests."""
    admin = User(
        email="admin@example.com",
        full_name="Test Admin",
        hashed_password=get_password_hash("Admin1234"),
        is_superuser=True,
        is_active=True,
        email_verified=True,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin

@pytest_asyncio.fixture()
async def admin_token(client, admin_user):
    """Devuelve un access token válido para el admin."""
    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": admin_user.email, "password": "Admin1234"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture()
def normal_user(db_session):
    from app.models.user import User
    from app.core.security import get_password_hash

    u = User(
        email="user@example.com",
        full_name="User Normal",
        hashed_password=get_password_hash("User1234"),
        is_superuser=False,
        is_active=True,
        email_verified=True,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u

@pytest_asyncio.fixture()
async def user_token(client, normal_user):
    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": normal_user.email, "password": "User1234"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]
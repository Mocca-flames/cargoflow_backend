import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.database import Base, get_db
from app.core.email import get_mailer
from app.main import app

TEST_DB = "cargo_flow_test"


class _NoopMailer:
    """Tests must never hit Brevo."""

    def __init__(self):
        self.background_tasks = None

    async def send(self, **kwargs):
        return {}

    def send_background(self, **kwargs):
        pass


def _url(db_name: str) -> str:
    base = settings.DATABASE_URL.rpartition("/")[0]
    return f"{base}/{db_name}"


@pytest.fixture(scope="session")
def engine():
    admin = create_engine(_url("postgres"))
    with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        exists = conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname = '{TEST_DB}'")).scalar()
        if not exists:
            conn.execute(text(f"CREATE DATABASE {TEST_DB}"))
    admin.dispose()
    eng = create_engine(_url(TEST_DB))
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture()
def db(engine):
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture()
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_mailer] = _NoopMailer
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

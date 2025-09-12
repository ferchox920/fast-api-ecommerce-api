# app/db/session.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

# Si la URL es SQLite, se necesita este argumento extra
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

# Crear el engine de SQLAlchemy
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    connect_args=connect_args
)

# Crear SessionLocal
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Declarative Base para los modelos
Base = declarative_base()

# Dependency para inyección de sesiones en FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

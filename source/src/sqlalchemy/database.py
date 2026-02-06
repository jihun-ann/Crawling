from scrapy.utils.project import get_project_settings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

settings = get_project_settings()

DATABASE_URL = f"postgresql://{settings.get("DB_USER")}:{settings.get("DB_PASSWORD")}@{settings.get("DB_URL")}:{settings.get("DB_PORT")}/{settings.get("DB_SCHEMA")}"

engine = create_engine(
    DATABASE_URL,
    pool_size=10, max_overflow=20
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()

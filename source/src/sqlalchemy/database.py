# PostgreSQL 연결 설정. 접속 정보는 settings(.env)에서 읽음
from scrapy.utils.project import get_project_settings
from sqlalchemy import URL, create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

settings = get_project_settings()

# URL.create: 비밀번호에 @ : / 같은 특수문자가 있어도 안전하게 이스케이프됨
DATABASE_URL = URL.create(
    "postgresql",
    username=settings.get("DB_USER"),
    password=settings.get("DB_PASSWORD"),
    host=settings.get("DB_URL"),
    port=int(settings.get("DB_PORT")),
    database=settings.get("DB_SCHEMA"),
)

# 커넥션 풀: 기본 10개 + 초과 시 최대 20개 추가
engine = create_engine(
    DATABASE_URL,
    pool_size=10, max_overflow=20
)

# 요청마다 세션을 만들 때 쓰는 팩토리 (api/main.py get_db)
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()   # 모든 테이블 모델(models/)의 부모 클래스

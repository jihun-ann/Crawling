# DB 스키마 변경 스크립트 실행. 실행: python -m source.src.sqlalchemy.db_script.migrate
from pathlib import Path

from source.src.sqlalchemy.database import engine

if __name__ == "__main__":
    sql = (Path(__file__).parent / "v2_place_review.sql").read_text(encoding="utf-8")
    with engine.begin() as conn:
        conn.exec_driver_sql(sql)
    print("migrated: v2_place_review.sql")

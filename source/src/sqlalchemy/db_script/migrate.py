# DB 스키마 변경 스크립트 실행. 실행: python -m source.src.sqlalchemy.db_script.migrate
from pathlib import Path

from source.src.sqlalchemy.database import engine

if __name__ == "__main__":
    # v2, v3 ... 순서대로 실행 (각 스크립트는 여러 번 실행해도 안전하게 작성)
    for f in sorted(Path(__file__).parent.glob("v*.sql")):
        with engine.begin() as conn:
            conn.exec_driver_sql(f.read_text(encoding="utf-8"))
        print(f"migrated: {f.name}")

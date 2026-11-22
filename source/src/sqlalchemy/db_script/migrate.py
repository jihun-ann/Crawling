# DB 스키마 변경 스크립트 실행. 실행: python -m source.src.sqlalchemy.db_script.migrate
import json
from pathlib import Path

from source.src.content_filter import content_hash
from source.src.pipelines import to_row
from source.src.sqlalchemy.crud import raw_post_crud
from source.src.sqlalchemy.database import engine

BLOG_CONTENT = Path(__file__).resolve().parents[2] / "blog_content"

if __name__ == "__main__":
    # v2, v3 ... 순서대로 실행 (각 스크립트는 여러 번 실행해도 안전하게 작성)
    for f in sorted(Path(__file__).parent.glob("v*.sql")):
        with engine.begin() as conn:
            conn.exec_driver_sql(f.read_text(encoding="utf-8"))
        print(f"migrated: {f.name}")

    # 예전 방식(blog_content/*/*.json) 원문 → raw_post. 이미 있는 글은 무시. 옮긴 뒤 blog_content 폴더는 지워도 됨
    files = sorted(BLOG_CONTENT.glob("*/*.json"))
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        d.setdefault("content_hash", content_hash(d.get("context")))
        raw_post_crud.insert(to_row(d))
    if files:
        print(f"imported json: {len(files)}")

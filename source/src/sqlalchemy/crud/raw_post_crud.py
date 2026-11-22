# raw_post(크롤링 원문) 조회/저장. 스파이더·파이프라인·로더가 공용으로 사용 (스키마: db_script/v4_raw_post.sql)
from sqlalchemy import text

from source.src.sqlalchemy.database import engine

COLUMNS = ("content_id", "platform", "url", "content_url", "title", "body", "keyword",
           "posted_at", "crawled_at", "content_hash", "excluded_reason")


def known_ids(ids):
    """이미 저장된 글 ID 집합. 스파이더가 같은 글을 다시 요청하지 않도록 사용."""
    ids = list(ids)
    if not ids:
        return set()
    with engine.connect() as c:
        return {r[0] for r in c.execute(text("SELECT content_id FROM raw_post WHERE content_id = ANY(:ids)"),
                                        {"ids": ids})}


def duplicate_of(content_hash):
    """같은 본문을 가진 원본 글 ID (중복으로 제외된 글은 원본에서 뺌). 없으면 None."""
    with engine.connect() as c:
        return c.execute(text("SELECT content_id FROM raw_post WHERE content_hash = :h "
                              "AND (excluded_reason IS NULL OR excluded_reason NOT LIKE 'duplicate%') LIMIT 1"),
                         {"h": content_hash}).scalar()


def insert(row: dict):
    """글 1건 저장. 같은 content_id가 있으면 무시."""
    row = {k: row.get(k) for k in COLUMNS}
    with engine.begin() as c:
        c.execute(text(f"INSERT INTO raw_post ({', '.join(COLUMNS)}) VALUES ({', '.join(':' + k for k in COLUMNS)}) "
                       "ON CONFLICT (content_id) DO NOTHING"), row)


def pending():
    """장소 매칭 대기 중인 글 (제외되지 않았고 아직 처리 안 한 글)."""
    with engine.connect() as c:
        return [dict(r._mapping) for r in c.execute(text(
            "SELECT * FROM raw_post WHERE processed_at IS NULL AND excluded_reason IS NULL ORDER BY crawled_at"))]


def mark_processed(content_id):
    with engine.begin() as c:
        c.execute(text("UPDATE raw_post SET processed_at = now() WHERE content_id = :id"), {"id": content_id})

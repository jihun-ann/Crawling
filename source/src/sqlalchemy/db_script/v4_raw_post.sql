-- v4: 크롤링 원문을 JSON 파일 대신 DB에 저장. 로더는 processed_at IS NULL 인 글만 1번씩 처리
CREATE TABLE IF NOT EXISTS raw_post (
    content_id      VARCHAR PRIMARY KEY,    -- 글 ID (content_filter.content_id, 기존 JSON 파일명과 같은 규칙)
    platform        VARCHAR NOT NULL,       -- naver / daum / web / youtube
    url             VARCHAR,                -- 글 URL
    content_url     VARCHAR,                -- 실제 본문 URL (iframe 등)
    title           VARCHAR,
    body            TEXT,
    keyword         VARCHAR,                -- 검색어. 주소 없는 글에서 지역 힌트로 사용
    posted_at       DATE,
    crawled_at      DATE DEFAULT current_date,
    content_hash    VARCHAR,                -- 본문 해시 (동일 본문 중복 판별)
    excluded_reason VARCHAR,                -- NULL=사용 / duplicate:* / ad:* / ai:* / llm:*
    processed_at    TIMESTAMPTZ             -- 장소 매칭 완료 시각. NULL이면 처리 대기
);
CREATE INDEX IF NOT EXISTS ix_raw_post_hash ON raw_post (content_hash);
CREATE INDEX IF NOT EXISTS ix_raw_post_pending ON raw_post (crawled_at) WHERE processed_at IS NULL AND excluded_reason IS NULL;

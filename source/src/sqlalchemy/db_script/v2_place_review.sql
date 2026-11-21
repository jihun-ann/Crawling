-- v2: 장소 매칭/추천용 스키마 변경. 여러 번 실행해도 안전 (IF NOT EXISTS / 타입 체크)
-- 실행: python -m source.src.sqlalchemy.db_script.migrate

-- 좌표를 문자열 → 실수로 (숫자가 아닌 값은 NULL)
DO $$
BEGIN
  IF (SELECT data_type FROM information_schema.columns WHERE table_name='place' AND column_name='latitude') <> 'double precision' THEN
    ALTER TABLE place ALTER COLUMN latitude TYPE DOUBLE PRECISION
      USING CASE WHEN latitude ~ '^-?[0-9]+(\.[0-9]+)?$' THEN latitude::double precision END;
    ALTER TABLE place ALTER COLUMN longitude TYPE DOUBLE PRECISION
      USING CASE WHEN longitude ~ '^-?[0-9]+(\.[0-9]+)?$' THEN longitude::double precision END;
  END IF;
END $$;

ALTER TABLE place ADD COLUMN IF NOT EXISTS category VARCHAR;                    -- 카페/맛집/소품샵/관광지/숙소/기타
ALTER TABLE place ADD COLUMN IF NOT EXISTS score DOUBLE PRECISION DEFAULT 0;   -- 추천 점수
ALTER TABLE place ADD COLUMN IF NOT EXISTS negative_ratio DOUBLE PRECISION DEFAULT 0;  -- 부정 후기 비율

-- place_id 자동 발급
CREATE SEQUENCE IF NOT EXISTS seq_place START 1;
SELECT setval('seq_place', GREATEST((SELECT COALESCE(MAX(place_id), 0) FROM place), 1));
ALTER TABLE place ALTER COLUMN place_id SET DEFAULT nextval('seq_place');

-- 같은 장소 중복 저장 방지 (상호명 + 도로명주소)
CREATE UNIQUE INDEX IF NOT EXISTS ux_place_name_addr ON place (name, location_detail);
CREATE INDEX IF NOT EXISTS ix_place_latlng ON place (latitude, longitude);
CREATE INDEX IF NOT EXISTS ix_place_category ON place (category);

-- 장소 ↔ 후기 글 연결 (어떤 글이 어떤 장소를 언급했는지)
CREATE TABLE IF NOT EXISTS place_review (
    place_id    INTEGER REFERENCES place (place_id) ON DELETE CASCADE,
    content_id  VARCHAR,            -- 글 ID (blog_content JSON 파일명)
    platform    VARCHAR,
    url         VARCHAR,
    title       VARCHAR,
    posted_at   DATE,               -- 글 작성일 (최근 30일 언급 수 계산)
    is_negative BOOLEAN DEFAULT FALSE,
    moods       TEXT,               -- 글에서 찾은 분위기 태그 JSON ["조용한", ...]
    PRIMARY KEY (place_id, content_id)
);

-- v5: 웹에서 코스를 검색한 지역 기록 → 매일 배치가 최근 검색된 지역을 우선 수집 (run_daily.py)
CREATE TABLE IF NOT EXISTS search_region (
    region           VARCHAR PRIMARY KEY,           -- 사용자가 입력한 지역 (위치 확인된 것만)
    search_count     INTEGER NOT NULL DEFAULT 1,
    last_searched_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

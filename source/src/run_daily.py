# 매일 실행하는 배치: 지역 × 키워드로 크롤링(네이버/다음·웹/유튜브) → (파이프라인에서 필터 후 raw_post 저장)
#                    → 새 글만 장소 매칭·DB 적재 → 점수 갱신
# 실행: python -m source.src.run_daily              # 지역 자동 선택 (아래 순서)
#       python -m source.src.run_daily 강릉 속초    # 지정한 지역만
# 자동 선택 순서 (중복 제거):
#   1) 웹에서 최근 30일 안에 검색된 지역 (search_region 테이블) — 수요 있는 곳 먼저
#   2) 직접 관리하는 목록 properties/regions.json
#   3) 전국 시/군/구(properties/sigungu_kr.json, 252곳)를 하루 NATIONWIDE_PER_DAY곳씩 순환 (약 25일에 한 바퀴)
# 이미 저장된 글은 다시 받지 않으므로 매일 같은 검색어를 돌려도 새 글만 쌓임. Windows 작업 스케줄러 등록은 README 참고
import datetime
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PROPERTIES = Path(__file__).resolve().parent / "properties"
KEYWORDS = ["맛집", "카페", "가볼만한곳", "소품샵"]      # 코스 종류(맛집/카페/관광지/소품샵)별 검색어
NATIONWIDE_PER_DAY = 10
SEARCHED_WITHIN_DAYS = 30


def crawl(*args):
    # scrapy는 한 프로세스에서 한 번만 실행 가능 → 스파이더마다 별도 프로세스
    subprocess.run([sys.executable, "-m", "scrapy", "crawl", *args], cwd=REPO_ROOT, check=False)


def merge_regions(searched, manual, nationwide, day, per_day=NATIONWIDE_PER_DAY):
    """검색된 지역 → 직접 관리 목록 → 전국 순환분(day마다 per_day곳씩 이어서) 순으로 합치고 중복 제거."""
    start = (day * per_day) % len(nationwide) if nationwide else 0
    today = (nationwide[start:] + nationwide[:start])[:per_day]
    return list(dict.fromkeys(r.strip() for r in [*searched, *manual, *today] if r and r.strip()))


def searched_regions():
    """웹에서 최근 검색된 지역 (많이 검색된 순). DB 오류면 빈 목록."""
    from sqlalchemy import text
    from source.src.sqlalchemy.database import engine
    try:
        with engine.connect() as c:
            return [r[0] for r in c.execute(text(
                "SELECT region FROM search_region WHERE last_searched_at >= now() - make_interval(days => :d) "
                "ORDER BY search_count DESC"), {"d": SEARCHED_WITHIN_DAYS})]
    except Exception as e:
        print(f"search_region 조회 실패: {e}")
        return []


def load(name):
    return json.loads((PROPERTIES / name).read_text(encoding="utf-8"))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        n = [f"지역{i}" for i in range(25)]
        assert merge_regions(["강릉", "속초"], ["강릉", "용인"], n, day=0, per_day=3) == ["강릉", "속초", "용인", "지역0", "지역1", "지역2"]
        assert merge_regions([], [], n, day=1, per_day=3) == ["지역3", "지역4", "지역5"]
        assert merge_regions([], [], n, day=8, per_day=3) == ["지역24", "지역0", "지역1"]     # 끝에서 처음으로 이어짐
        assert merge_regions([" 강릉 ", ""], ["강릉"], [], day=0) == ["강릉"]
        print("ok")
        sys.exit()

    regions = sys.argv[1:] or merge_regions(searched_regions(), load("regions.json"), load("sigungu_kr.json"),
                                            datetime.date.today().toordinal())
    print(f"수집 지역 {len(regions)}곳: {', '.join(regions)}", flush=True)
    for region in regions:
        for keyword in KEYWORDS:
            query = f"query={region} {keyword}"
            crawl("naver_crawling", "-a", query)          # 네이버 검색 API (하루 25,000회 무료)
            crawl("daum_crawling", "-a", query)           # KAKAO_REST_API_KEY 없으면 건너뜀
        crawl("youtube_crawling", "-a", f"query={region} 여행")   # 하루 검색 약 90회 한도라 지역당 1번. 키 없으면 건너뜀

    from source.src.sqlalchemy.services.blog_content_loader import BlogContentLoader
    BlogContentLoader().run()

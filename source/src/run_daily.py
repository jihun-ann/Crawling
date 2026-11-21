# 매일 실행하는 배치: 크롤링 → (파이프라인에서 필터/저장) → 장소 매칭·DB 적재 → 점수 갱신
# 실행: python -m source.src.run_daily 서울특별시 [강원특별자치도 ...]
# Windows 작업 스케줄러 등록 방법은 README 참고
import subprocess
import sys
from pathlib import Path

from source.src.sqlalchemy.services.blog_content_loader import BlogContentLoader

REPO_ROOT = Path(__file__).resolve().parents[2]

if __name__ == "__main__":
    provinces = sys.argv[1:] or ["서울특별시"]
    for prov in provinces:
        # scrapy는 한 프로세스에서 한 번만 실행 가능 → 지역마다 별도 프로세스
        subprocess.run([sys.executable, "-m", "scrapy", "crawl", "naver_crawling", "-a", f"prov={prov}"],
                       cwd=REPO_ROOT, check=False)
    BlogContentLoader().file_load()

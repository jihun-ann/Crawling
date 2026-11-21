# Scrapy 설정 + 프로젝트 공용 설정 (크롤러, API, 로더가 모두 get_project_settings()로 읽음)
# 문서: https://docs.scrapy.org/en/latest/topics/settings.html
import os
from pathlib import Path

from dotenv import load_dotenv

# 레포 루트의 .env에서 DB 접속 정보 / API 키를 읽음 (.env는 git 제외, 양식은 .env.example)
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

BOT_NAME = "source"
BASE_DIR = str(Path(__file__).resolve().parents[2])  # 레포 루트. 크롤링 결과 저장 경로 기준

SPIDER_MODULES = ["source.src.spiders"]
NEWSPIDER_MODULE = "source.src.spiders"

LOG_LEVEL = "INFO"

# PostgreSQL 접속 정보 (sqlalchemy/database.py)
DB_URL = os.getenv("DB_URL")
DB_PORT = os.getenv("DB_PORT")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_SCHEMA = os.getenv("DB_SCHEMA")

# 통계청 SGIS: 시/구/동 목록 조회 → 크롤링 검색어 생성 (NaverSpider.location_list)
SGIS_CLIENT_ID = os.getenv("SGIS_CLIENT_ID")
SGIS_CLIENT_KEY = os.getenv("SGIS_CLIENT_KEY")

# 네이버 개발자센터: 지역검색 API로 블로그 속 장소 확인 (blog_content_loader.retrive_place)
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_KEY = os.getenv("NAVER_CLIENT_KEY")

# 카카오: 다음 블로그(Tistory 등) 검색 (spiders/DaumBlogSpider)
KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY")

# 유튜브 Data API v3 (spiders/YoutubeSpider)
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# 광고/AI글 Claude 2차 판정 (llm_check.py). 1이면 켜짐 → API 비용 발생. 키는 ANTHROPIC_API_KEY
AI_CHECK_WITH_LLM = os.getenv("AI_CHECK_WITH_LLM") == "1"

# 요청 설정
ROBOTSTXT_OBEY = False
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
COOKIES_ENABLED = False

# 동시 요청 수 / 요청 간격 (대상 사이트 부하 방지)
CONCURRENT_REQUESTS = 32
CONCURRENT_REQUESTS_PER_DOMAIN = 16
DOWNLOAD_DELAY = 0.5
RANDOMIZE_DOWNLOAD_DELAY = True     # 지연 시간을 0.5~1.5배로 랜덤 적용

# 너비 우선(BFS) 크롤링: 검색 결과 페이지를 먼저 다 돌고 본문으로 내려감
DEPTH_PRIORITY = 1
SCHEDULER_DISK_QUEUE = 'scrapy.squeues.PickleFifoDiskQueue'
SCHEDULER_MEMORY_QUEUE = 'scrapy.squeues.FifoMemoryQueue'

# 크롤링 결과 처리: 중복/광고/AI글 판별 후 blog_content/{platform}/*.json 저장
ITEM_PIPELINES = {
   "source.src.pipelines.SrcPipeline": 300,
}

FEED_EXPORT_ENCODING = "utf-8"

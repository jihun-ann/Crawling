# 🐍Crawling | Python Toy Project
## 📌Purpose
This project crawls Naver blog posts, calculates an interest score based on the number of blog posts, and stores the processed data in a PostgreSQL database.

## 🎄To-be Architecture
![img.png](img.png)

## 🛠 Tech Stack
- ***Python***
- ***Scrapy***
- ***FastAPI***
- ***PostgreSQL***
- ***SQLAlchemy***

### Setup
>pip install -r requirements.txt

`.env.example`을 `.env`로 복사하고 DB 접속 정보와 API 키를 채웁니다.

### Crawling (API와 별도 실행)
>scrapy crawl naver_crawling -a prov=서울특별시

### API
>python -m uvicorn source.src.api.main:app --port 8000

### Web
>cd web && npm install && npm run dev

`web/.env.local` (선택)
- `API_URL` : 백엔드 주소 (기본 `http://localhost:8000`)
- `NEXT_PUBLIC_NAVER_MAP_CLIENT_ID` : 네이버 지도 키. 없으면 지도 없이 목록만 표시

### DB 스키마 변경 (최초 1회)
>python -m source.src.sqlalchemy.db_script.migrate

### 매일 배치 (크롤링 → 장소 적재 → 점수)
>python -m source.src.run_daily 서울특별시

Windows 작업 스케줄러 등록 (매일 04:00):
>schtasks /Create /SC DAILY /ST 04:00 /TN CrawlingDaily /TR "cmd /c cd /d C:\WorkSpace\Crawling && (if not exist logs mkdir logs) && .venv\Scripts\python -m source.src.run_daily 서울특별시 >> logs\daily.log 2>&1"
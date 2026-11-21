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
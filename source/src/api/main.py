# 웹(Next.js)이 호출하는 백엔드 API. 실행: python -m uvicorn source.src.api.main:app --port 8000 (문서: /docs)
from datetime import datetime, timedelta
from typing import Literal

from fastapi import FastAPI, Depends, Query
from sqlalchemy.orm import Session
import logging

from source.src.sqlalchemy.crud import place_crud
from source.src.sqlalchemy import database

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)
app = FastAPI()

def get_db():
    """요청마다 DB 세션을 열고 응답 후 닫음. 엔드포인트에서 Depends(get_db)로 사용."""
    db_session = database.SessionLocal()
    try:
        yield db_session
    finally:
        db_session.close()

# 코스 기본 순서 (출발지 다음) / 장소당 머무는 시간(분)
COURSE_CATEGORIES = ["관광지", "카페", "소품샵", "맛집"]
STAY_MINUTES = 90


def _mock_place(place_id, category, n):
    """목업 장소 데이터 생성 (place DB 연결 전 임시)."""
    return {"id": place_id, "name": f"예시 {category} {chr(65 + n)}", "category": category, "address": "주소 준비 중"}


@app.get("/courses/recommend")
def recommend_course(
    mode: Literal["region", "transport", "mood", "random"] = "random",
    region: str | None = None,
    stay: str | None = None,
    transport: str | None = None,
    mood: str | None = None,
    from_: str | None = Query(None, alias="from"),
    start: str = Query("09:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$"),
):
    """코스 추천. 웹 /course 화면이 호출.

    mode: region(지역) / transport(교통수단) / mood(분위기) / random
    region·stay: 지역·숙소, transport: 교통수단, mood: 분위기, from: 출발지, start: 출발 시간(HH:MM)
    응답: {title, steps: [{time, category, place, alternatives}]}
    """
    # ponytail: 목업 응답. place DB 채워지면 지역/반경/업종 조건으로 조회해 순서대로 채우기
    t0 = datetime.strptime(start, "%H:%M")
    origin = stay or region or from_ or "출발지"
    steps = [{"time": start, "category": "출발",
              "place": {"id": 0, "name": origin, "category": "출발", "address": ""}, "alternatives": []}]
    for i, c in enumerate(COURSE_CATEGORIES):
        steps.append({
            "time": (t0 + timedelta(minutes=30 + i * STAY_MINUTES)).strftime("%H:%M"),
            "category": c,
            "place": _mock_place(i * 10 + 1, c, 0),
            "alternatives": [_mock_place(i * 10 + 1 + n, c, n) for n in (1, 2)],
        })
    title = f"{region} 코스" if region else f"{mood} 분위기 코스" if mood else "추천 코스"
    return {"title": title, "steps": steps}


# DB 연결 테스트용: place_id=1 조회
@app.get("/test2")
def get_place(db: Session = Depends(get_db)):
    place_db = place_crud
    place = place_db.get_place_id(db,1)
    return {"code":200, "response":place}


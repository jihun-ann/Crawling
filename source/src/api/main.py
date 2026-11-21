# 웹(Next.js)이 호출하는 백엔드 API. 실행: python -m uvicorn source.src.api.main:app --port 8000 (문서: /docs)
import json
import logging
import math
import random
import re
from typing import Literal

import requests
from fastapi import FastAPI, Depends, Query, HTTPException
from scrapy.utils.project import get_project_settings
from sqlalchemy.orm import Session

from source.src.api.course import COURSE_ORDER, SEARCH_RADIUS_KM, DEFAULT_TRANSPORT, build_course
from source.src.sqlalchemy import database
from source.src.sqlalchemy.models.place_model import Place, PlaceReview

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)
app = FastAPI()
settings = get_project_settings()

Text = Query(None, max_length=50)   # 사용자 입력 문자열 공통 제한


def get_db():
    """요청마다 DB 세션을 열고 응답 후 닫음. 엔드포인트에서 Depends(get_db)로 사용."""
    db_session = database.SessionLocal()
    try:
        yield db_session
    finally:
        db_session.close()


def place_dict(p: Place):
    """DB Place → API 응답용 dict (웹 lib/course.ts의 Place 타입과 같은 모양)."""
    return {"id": p.place_id, "name": p.name, "category": p.category, "address": p.location_detail or "",
            "lat": p.latitude, "lng": p.longitude, "score": round(p.score or 0, 2),
            "moods": json.loads(p.keywords) if p.keywords and p.keywords.startswith("[") else [],
            "review_count": p.review_count_blog or 0, "negative_ratio": p.negative_ratio or 0,
            "phone": p.phone_number}


def places_near(db: Session, lat, lng, radius_km, category=None):
    """좌표 반경 안의 장소. SQL로 사각형 범위만 자르고 정확한 거리는 course.py에서 계산."""
    # ponytail: PostGIS 없이 위경도 사각형 조회. 장소가 수십만 개 넘으면 PostGIS + 공간 인덱스로
    dlat = radius_km / 111
    dlng = radius_km / (111 * math.cos(math.radians(lat)))
    q = db.query(Place).filter(Place.latitude.between(lat - dlat, lat + dlat),
                               Place.longitude.between(lng - dlng, lng + dlng))
    if category:
        q = q.filter(Place.category == category)
    return q.all()


def geocode(query):
    """장소명/지역명 → 좌표. 네이버 지역검색 첫 결과 사용. 못 찾으면 None."""
    res = requests.get("https://openapi.naver.com/v1/search/local.json", params={"query": query, "display": 1},
                       headers={"X-Naver-Client-Id": settings.get("NAVER_CLIENT_ID"),
                                "X-Naver-Client-Secret": settings.get("NAVER_CLIENT_KEY")}, timeout=10)
    items = res.json().get("items", []) if res.status_code == 200 else []
    if not items:
        return None
    it = items[0]
    return {"name": re.sub(r"<[^>]+>", "", it["title"]), "address": it.get("roadAddress") or it.get("address", ""),
            "lat": int(it["mapy"]) / 10_000_000, "lng": int(it["mapx"]) / 10_000_000}


@app.get("/places")
def list_places(region: str | None = Text, category: str | None = Text,
                lat: float | None = Query(None, ge=-90, le=90), lng: float | None = Query(None, ge=-180, le=180),
                radius_km: float = Query(3, gt=0, le=50), limit: int = Query(50, ge=1, le=200),
                db: Session = Depends(get_db)):
    """장소 검색. 좌표+반경 또는 주소에 포함된 지역명(region)으로, 업종(category)으로 거르고 점수순 정렬."""
    if lat is not None and lng is not None:
        rows = places_near(db, lat, lng, radius_km, category)
    else:
        q = db.query(Place)
        if region:
            q = q.filter(Place.location_detail.contains(region))
        if category:
            q = q.filter(Place.category == category)
        rows = q.all()
    rows.sort(key=lambda p: p.score or 0, reverse=True)
    return [place_dict(p) for p in rows[:limit]]


@app.get("/places/{place_id}")
def get_place(place_id: int, db: Session = Depends(get_db)):
    """장소 상세 + 연결된 후기 글 목록(최신순)."""
    p = db.get(Place, place_id)
    if not p:
        raise HTTPException(404, "장소를 찾을 수 없습니다")
    reviews = (db.query(PlaceReview).filter_by(place_id=place_id)
               .order_by(PlaceReview.posted_at.desc().nulls_last()).all())
    return {**place_dict(p), "naver_category": p.type,
            "reviews": [{"title": r.title, "url": r.url, "platform": r.platform,
                         "posted_at": r.posted_at.isoformat() if r.posted_at else None,
                         "is_negative": r.is_negative} for r in reviews]}


@app.get("/courses/recommend")
def recommend_course(
    mode: Literal["region", "transport", "mood", "random"] = "random",
    region: str | None = Text,
    stay: str | None = Text,
    transport: str | None = Text,
    mood: str | None = Text,
    from_: str | None = Query(None, alias="from", max_length=50),
    start: str = Query("09:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$"),
    db: Session = Depends(get_db),
):
    """코스 추천. 웹 /course 화면이 호출.

    mode: region(지역) / transport(교통수단) / mood(분위기) / random
    region·stay: 지역·숙소, transport: 교통수단, mood: 분위기, from: 출발지, start: 출발 시간(HH:MM)
    응답: {title, message, steps: [{time, category, travel_min, place, alternatives}]}
    """
    if mode == "random":
        top = (db.query(Place).filter(Place.category.in_(COURSE_ORDER), Place.latitude.isnot(None))
               .order_by(Place.score.desc()).limit(20).all())
        if not top:
            return {"title": "랜덤 코스", "message": "아직 추천할 장소 데이터가 없어요.", "steps": []}
        anchor = random.choice(top)
        origin = {"name": f"{anchor.name} 근처", "address": anchor.location_detail,
                  "lat": anchor.latitude, "lng": anchor.longitude}
        title = f"랜덤 코스 · {anchor.location_city or ''}".strip(" ·")
    else:
        query = stay or from_ or region
        if not query:
            raise HTTPException(422, "지역, 숙소 또는 출발지를 입력해 주세요")
        origin = geocode(" ".join(filter(None, [region if stay else None, query])))
        if not origin:
            raise HTTPException(404, f"'{query}' 위치를 찾지 못했어요")
        origin["name"] = query
        title = (f"{region} 코스" if region else f"{mood} 분위기 코스" if mood
                 else f"{transport}로 떠나는 코스" if transport else "추천 코스")

    radius = SEARCH_RADIUS_KM.get(transport or DEFAULT_TRANSPORT, SEARCH_RADIUS_KM[DEFAULT_TRANSPORT])
    places = [place_dict(p) for p in places_near(db, origin["lat"], origin["lng"], radius)]
    steps = build_course(origin, places, start, transport, mood)
    message = None if len(steps) > 1 else "이 주변에는 아직 추천할 장소 데이터가 없어요. 다른 지역을 입력해 보세요."
    return {"title": title, "message": message, "steps": steps}

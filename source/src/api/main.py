# 웹(Next.js)이 호출하는 백엔드 API. 실행: python -m uvicorn source.src.api.main:app --port 8000 (문서: /docs)
import datetime
import json
import logging
import math
import random
import re
from pathlib import Path
from typing import Literal

import requests
from fastapi import FastAPI, Depends, Query, HTTPException
from scrapy.utils.project import get_project_settings
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from source.src.api.course import (COURSE_ORDER, SEARCH_RADIUS_KM, DEFAULT_TRANSPORT, DEFAULT_END, ROUTE_MAX_DETOUR_KM,
                                   MEAL_WINDOWS, ARRIVAL_ZONE_KM, build_course, build_trip, haversine_km)
from source.src.api.routing import drive_route
from source.src.content_filter import spot_type as spot_type_of
from source.src.hours import WEEKDAYS
from source.src.sqlalchemy import database
from source.src.sqlalchemy.models.place_model import Place, PlaceReview

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)
app = FastAPI()
settings = get_project_settings()

def Text():
    return Query(None, max_length=50)   # 사용자 입력 문자열 공통 제한 (파라미터마다 새 객체 필요)
KST = datetime.timezone(datetime.timedelta(hours=9))   # '오늘' 기준 (서버 시간대와 무관하게 한국 시간)


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
            "phone": p.phone_number, "city": p.location_city,
            # hours.py 저장 형식. 예전 테스트 데이터('09:00~22:00' 같은 문자열)는 정보 없음으로 처리
            "hours": json.loads(p.business_hours) if (p.business_hours or "").startswith("{") else None}


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


def naver_local(query, display=1, sort="random"):
    """네이버 지역검색 (하루 25,000회 무료) → [{name, category, address, lat, lng}]. sort: random(정확도)/comment(리뷰 많은 순)."""
    res = requests.get("https://openapi.naver.com/v1/search/local.json",
                       params={"query": query, "display": display, "sort": sort},
                       headers={"X-Naver-Client-Id": settings.get("NAVER_CLIENT_ID"),
                                "X-Naver-Client-Secret": settings.get("NAVER_CLIENT_KEY")}, timeout=10)
    items = res.json().get("items", []) if res.status_code == 200 else []
    return [{"name": re.sub(r"<[^>]+>", "", it["title"]), "category": it.get("category") or "",
             "address": it.get("roadAddress") or it.get("address", ""),
             "lat": int(it["mapy"]) / 10_000_000, "lng": int(it["mapx"]) / 10_000_000} for it in items]


def geocode(query):
    """장소명/지역명 → 좌표. 네이버 지역검색 첫 결과 사용. 못 찾으면 None."""
    found = naver_local(query)
    return found[0] if found else None


SIGUNGU_COORDS = json.loads((Path(__file__).resolve().parents[1] / "properties" / "sigungu_coords.json")
                            .read_text(encoding="utf-8"))     # 전국 시/군/구 → 시/군/구청 좌표


def meal_places_on_way(db: Session, home, dest, start):
    """가는 길에 점심/저녁 시간대에 지나는 시/군/구의 맛집 (네이버 지역검색, 리뷰 많은 순 5곳).

    DB에 데이터가 없는 구간을 채우고, 그 시/군/구를 search_region에 기록해 매일 배치가 수집하게 함.
    시각은 들르는 곳 없이 바로 갈 때 기준 (실제로 고르는 건 build_route가 경로·영업시간 보고 판단)
    """
    route = drive_route((home["lat"], home["lng"]), (dest["lat"], dest["lng"]))
    if not route:
        return []
    t0 = int(start[:2]) * 60 + int(start[3:])
    found = []
    for lo, hi in MEAL_WINDOWS:
        pt = next(((lat, lng) for lat, lng, m in route["points"]
                   if lo <= t0 + m <= hi and haversine_km(lat, lng, dest["lat"], dest["lng"]) >= ARRIVAL_ZONE_KM), None)
        if not pt:
            continue
        region = min(SIGUNGU_COORDS, key=lambda k: haversine_km(*pt, *SIGUNGU_COORDS[k]))
        record_search_region(db, region)
        for p in naver_local(f"{region} 맛집", display=5, sort="comment"):
            # DB에 없는 장소 → 음수 id(상세 페이지 링크 없음), 후기 점수 없음(1.0), 영업시간 모름
            found.append({**p, "id": -(abs(hash((p["name"], p["address"]))) % 10**9), "category": "맛집", "score": 1.0,
                          "moods": [], "review_count": 0, "negative_ratio": 0, "hours": None, "city": None, "phone": None})
    return found


SPOT_DIST_WEIGHT = 0.05     # 가볼만한 곳을 고를 때 1km당 깎는 점수 (일부러 찾아가는 곳이라 일반 장소보다 약하게)


def spots(db: Session, kind=None):
    """저장된 가볼만한 곳(관광지) + 세부 종류(spot_type, 네이버 업종 마지막 단계). kind를 주면 그 종류만."""
    rows = db.query(Place).filter(Place.category == "관광지", Place.latitude.isnot(None)).all()
    # category를 세부 종류로 바꿔 코스 단계에 "테마파크", "수목원,식물원"처럼 표시
    items = [{**place_dict(p), "spot_type": (t := spot_type_of(p.type)), "category": t} for p in rows]
    return [x for x in items if not kind or x["spot_type"] == kind]


def pick_spot(db: Session, kind, origin=None):
    """종류(kind)의 가볼만한 곳 중 하나 선택. 출발지가 있으면 가깝고 점수 높은 곳, 없으면 점수 가장 높은 곳."""
    items = spots(db, kind)
    if not items:
        return None
    if not origin:
        return max(items, key=lambda x: x["score"])
    return max(items, key=lambda x: x["score"] - SPOT_DIST_WEIGHT *
               haversine_km(origin["lat"], origin["lng"], x["lat"], x["lng"]))


@app.get("/spot-types")
def list_spot_types(db: Session = Depends(get_db)):
    """가볼만한 곳 세부 종류 목록 (저장된 데이터에 있는 것만, 많은 순). 웹 선택지용, 장소 이름은 내려주지 않음."""
    counts = {}
    for x in spots(db):
        counts[x["spot_type"]] = counts.get(x["spot_type"], 0) + 1
    return [{"type": t, "count": n} for t, n in sorted(counts.items(), key=lambda kv: -kv[1])]


@app.get("/places")
def list_places(region: str | None = Text(), category: str | None = Text(),
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
    region: str | None = Text(),
    stay: str | None = Text(),
    transport: str | None = Text(),
    mood: str | None = Text(),
    from_: str | None = Query(None, alias="from", max_length=50),
    start: str = Query("09:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$"),
    end: str = Query(DEFAULT_END, pattern=r"^([01]\d|2[0-3]):[0-5]\d$"),
    date: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    spot_type: str | None = Text(),
    db: Session = Depends(get_db),
):
    """코스 추천. 웹 /course 화면이 호출. 크롤링으로 저장된 장소(place)만 추천.

    mode: region(지역) / transport(교통수단) / mood(분위기) / random
    region·stay: 지역·숙소, transport: 교통수단, mood: 분위기, start/end: 출발·종료 시간(HH:MM)
    from: region 모드에선 집 등 출발지(선택) → 여행지까지 가는 길(밥·카페 들르기)부터 코스에 포함 / 다른 모드에선 코스 시작점
    date: 출발 날짜(YYYY-MM-DD, 없으면 오늘) → 그 요일 영업시간으로 휴무/영업 전후 장소 제외
    spot_type: 가볼만한 곳 세부 종류(GET /spot-types, 예: 테마파크/수목원,식물원). 그 종류 중 가깝고 점수 높은 곳을 첫 방문지로
    응답: {title, message, weekday, steps: [{time, category, travel_min, place, alternatives, hours_today, warning}]}
    """
    try:
        day = datetime.date.fromisoformat(date) if date else datetime.datetime.now(KST).date()
    except ValueError:
        raise HTTPException(422, "날짜 형식이 올바르지 않아요")
    weekday = WEEKDAYS[day.weekday()]
    if end <= start:        # "HH:MM" 형식이 같아서 문자열 비교 = 시간 비교
        raise HTTPException(422, "종료 시간은 출발 시간보다 늦어야 해요")
    home = from_ if mode == "region" else None

    anchor = None
    if mode == "random":
        top = (db.query(Place).filter(Place.category.in_(COURSE_ORDER), Place.latitude.isnot(None))
               .order_by(Place.score.desc()).limit(20).all())
        if not top:
            return {"title": "랜덤 코스", "message": "아직 추천할 장소 데이터가 없어요.", "steps": []}
        pick = random.choice(top)
        origin = {"name": f"{pick.name} 근처", "address": pick.location_detail,
                  "lat": pick.latitude, "lng": pick.longitude}
        title = f"랜덤 코스 · {pick.location_city or ''}".strip(" ·")
    else:
        query = stay or region if mode == "region" else from_    # region 모드의 from은 집(가는 길 시작점)
        origin = geocode_named(" ".join(filter(None, [region if stay else None, query])), query) if query else None
        if region and mode == "region":
            record_search_region(db, region)                    # 매일 배치가 이 지역을 우선 수집
        if spot_type:
            anchor = pick_spot(db, spot_type, origin)
            if not anchor:
                raise HTTPException(404, f"아직 수집된 '{spot_type}' 장소가 없어요")
            origin = origin or anchor                           # 숙소/지역 없이 종류만 → 그 장소에서 시작
        if not origin:
            raise HTTPException(422, "지역, 숙소, 출발지 또는 가볼만한 곳 종류를 입력해 주세요")
        title = (f"{region + ' ' if region else ''}{spot_type} 코스" if spot_type else f"{region} 코스" if region
                 else f"{mood} 분위기 코스" if mood else f"{transport}로 떠나는 코스" if transport else "추천 코스")

    # 테마파크가 있으면 그 주변에서, 없으면 출발지 주변에서 후보를 찾음
    center = anchor or origin
    radius = SEARCH_RADIUS_KM.get(transport or DEFAULT_TRANSPORT, SEARCH_RADIUS_KM[DEFAULT_TRANSPORT])
    places = [place_dict(p) for p in places_near(db, center["lat"], center["lng"], radius)]
    if home:
        # 집 → 여행지: 두 지점 사이(+우회 허용 거리) 장소 중 가는 길에 들를 곳 + 도착 후 여행지 코스
        start_point = geocode_named(home, home)
        mid_lat, mid_lng = (start_point["lat"] + center["lat"]) / 2, (start_point["lng"] + center["lng"]) / 2
        half = haversine_km(start_point["lat"], start_point["lng"], center["lat"], center["lng"]) / 2
        route_places = [place_dict(p) for p in places_near(db, mid_lat, mid_lng, half + ROUTE_MAX_DETOUR_KM)]
        route_places += meal_places_on_way(db, start_point, center, start)
        steps = build_trip(start_point, origin, route_places, places, start, transport, mood, weekday, anchor, end,
                           route_fn=drive_route)
    else:
        steps = build_course(origin, places, start, transport, mood, weekday, anchor, end)
    picked = [s for s in steps if s["place"]["id"] not in (0, (anchor or {}).get("id"))]
    message = (None if picked
               else "이 시간대에 영업 중인 추천 장소를 주변에서 찾지 못했어요. 출발 시간이나 날짜를 바꿔 보세요." if places
               else "이 주변에는 아직 추천할 장소 데이터가 없어요. 다른 지역을 입력해 보세요.")
    if home:
        message = " ".join(filter(None, [message, "가는 길 이동 시간은 자동차 기준이에요 (실시간 교통 미반영)."]))
    return {"title": title, "message": message, "weekday": weekday, "date": day.isoformat(), "steps": steps}


def record_search_region(db: Session, region):
    """검색된 지역 기록 (search_region). 기록 실패해도 추천은 계속."""
    try:
        db.execute(sql_text("INSERT INTO search_region (region) VALUES (:r) ON CONFLICT (region) DO UPDATE "
                            "SET search_count = search_region.search_count + 1, last_searched_at = now()"),
                   {"r": region.strip()})
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"search_region 기록 실패|{region}|{e}")


def geocode_named(query, name):
    """geocode + 화면에 보일 이름 지정. 못 찾으면 404."""
    p = geocode(query)
    if not p:
        raise HTTPException(404, f"'{name}' 위치를 찾지 못했어요")
    p["name"] = name
    return p

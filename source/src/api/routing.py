# 실제 도로 경로와 소요 시간 (자동차). OSRM(오픈소스 길찾기, OpenStreetMap 도로 데이터) 공개 서버 사용, 키 불필요
# ponytail: 공개 데모 서버라 초당 1회·운영 비권장·실시간 교통 미반영. 운영 시 OSRM 자체 서버나 카카오모빌리티 길찾기(권한 신청)로 교체
import functools
import logging

import requests

from source.src.api.course import haversine_km

logger = logging.getLogger(__name__)
OSRM = "https://router.project-osrm.org/route/v1/driving"


@functools.lru_cache(maxsize=512)
def _osrm(a, b):
    res = requests.get(f"{OSRM}/{a[1]},{a[0]};{b[1]},{b[0]}", params={"overview": "simplified", "geometries": "geojson"},
                       headers={"User-Agent": "course-recommender"}, timeout=10)
    res.raise_for_status()
    route = res.json()["routes"][0]
    return route["duration"] / 60, [(lat, lng) for lng, lat in route["geometry"]["coordinates"]]


def drive_route(a, b):
    """(lat, lng) → (lat, lng) 자동차 경로. {"minutes": 총 소요(분), "points": [(lat, lng, 출발 후 분)]}. 실패하면 None.

    경로 위 각 지점의 시각 = 총 소요 × (그 지점까지 거리 / 전체 거리)
    """
    try:
        minutes, coords = _osrm((round(a[0], 5), round(a[1], 5)), (round(b[0], 5), round(b[1], 5)))
    except Exception as e:
        logger.warning(f"경로 조회 실패, 직선거리 추정으로 대체|{e}")
        return None
    dist = [0.0]
    for p, q in zip(coords, coords[1:]):
        dist.append(dist[-1] + haversine_km(*p, *q))
    total = dist[-1] or 1
    return {"minutes": round(minutes), "points": [(lat, lng, minutes * d / total) for (lat, lng), d in zip(coords, dist)]}

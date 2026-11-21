import datetime
import json
import logging
import re
import time
import urllib.parse
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from scrapy.utils.project import get_project_settings

from source.src.content_filter import is_negative, mood_tags, normalize_category
from source.src.hours import open_days, parse_naver_hours
from source.src.sqlalchemy import database
from source.src.sqlalchemy.crud import place_crud

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# 본문에서 도로명 주소 찾는 정규식: (시/도) 시/군/구 + 도로명 + 건물번호
SI_DO = r'(?:서울(?:특별시|시)|부산(?:광역시|시)|대구(?:광역시|시)|인천(?:광역시|시)|광주(?:광역시|시)|대전(?:광역시|시)|울산(?:광역시|시)|세종(?:특별자치시|시)|경기(?:도)|강원(?:특별자치도|도)|충북(?:도)|충청북도|충남(?:도)|충청남도|전북(?:도)|전라북도|전남(?:도)|전라남도|경북(?:도)|경상북도|경남(?:도)|경상남도|제주(?:특별자치도|도))'
SI_GUN_GU = r'[가-힣]+(?:시|군|구)'
ROAD = r'[가-힣\d]+(?:로|길)(?:[ \t]*\d+번?길)?'
BUILDING_INFO = r'\d{1,4}(?:-\d{1,4})?'
ADDRESS_PATTERN = re.compile(rf'(?:(?:{SI_DO}[ \t]+)?{SI_GUN_GU}[ \t]+){ROAD}[ \t]+{BUILDING_INFO}')

IGNORE_PLACE_KEYWORDS = ("주차장", "병원", "유치원", "약국", "은행", "아파트", "호선", "주민센터", "학교")
MOBILE_UA = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148"}


def _nospace(s):
    return s.replace(" ", "")


class BlogContentLoader:
    """크롤링된 블로그 JSON → 본문 속 주소/상호명 추출 → 네이버 지역검색으로 실제 장소 확인 → place / place_review 저장 → 점수 갱신.

    실행: python -m source.src.sqlalchemy.services.blog_content_loader
    """
    def __init__(self):
        settings = get_project_settings()
        self.path = Path(settings.get("BASE_DIR"))/"source"/"src"/"blog_content"
        self.headers = {"X-Naver-Client-Id": settings.get("NAVER_CLIENT_ID"),
                        "X-Naver-Client-Secret": settings.get("NAVER_CLIENT_KEY")}
        self.db = database.SessionLocal()

    def file_load(self):
        """저장된 JSON 전체 처리 후 점수 갱신. 파일 하나가 실패해도 나머지는 계속."""
        saved = 0
        for file in sorted(self.path.glob("*/*.json")):
            if file.name.startswith("s_"):
                continue
            try:
                saved += self.load_file(file)
            except Exception as e:
                self.db.rollback()
                logger.exception(f"BlogContentLoader|load_file Error|{file.name}|{e}")
        updated = place_crud.update_scores(self.db)
        logger.info(f"BlogContentLoader|done|장소 연결 {saved}건|점수 갱신 {updated}곳")

    def load_file(self, file):
        """글 1개 처리. 본문의 주소마다 장소를 찾아 저장하고, 저장한 장소 수 반환. 제외된 글은 건너뜀."""
        data = json.loads(file.read_text(encoding="utf-8"))
        if data.get("excluded_reason"):
            return 0
        text = data["context"]
        review = {
            "content_id": data["filename"],
            "platform": data["platform"],
            "url": data["init_url"],
            "title": (data.get("title") or "").strip(),
            "posted_at": data.get("posted_at"),
            "is_negative": is_negative(text),
            "moods": json.dumps(mood_tags(text), ensure_ascii=False),
        }

        saved = 0
        for address in self.unique_addresses(text):
            place_name = self.pick_place_name(address, text)
            if not place_name:
                continue
            place = self.retrive_place(place_name, address)
            if not place:
                continue
            place_id = place_crud.save_place(self.db, place)
            place_crud.add_review(self.db, {**review, "place_id": place_id})
            logger.info(f"BlogContentLoader|saved|{place['name']}|{place['category']}|{data['filename']}")
            saved += 1
        return saved

    def unique_addresses(self, text):
        """본문 속 도로명 주소 목록. 같은 주소의 다른 표기(시/도 유무 등)는 하나로."""
        kept = []
        for add in ADDRESS_PATTERN.findall(text):
            if not any(_nospace(add) in _nospace(k) or _nospace(k) in _nospace(add) for k in kept):
                kept.append(add)
        return kept

    def pick_place_name(self, address, text):
        """주소에 있는 장소 후보 중 본문에 가장 많이 나온 이름. 없거나 제외 업종이면 None."""
        candidates = self.find_place_name(address)
        if not candidates:
            logger.info(f"BlogContentLoader|주소에 장소 후보 없음|{address}")
            return None
        counts = {c.get_text(): text.count(c.get_text()) for c in candidates if c.get_text()}
        counts = {k: v for k, v in counts.items() if v}
        if not counts:
            return None
        name = max(counts, key=counts.get)
        return None if any(k in name for k in IGNORE_PLACE_KEYWORDS) else name

    def retrive_place(self, place_name, address):
        """네이버 지역검색 API로 (상호명 + 주소) 검색 → 도로명 주소가 일치하는 첫 결과를 place 컬럼 dict로. 없으면 None."""
        res = requests.get("https://openapi.naver.com/v1/search/local.json",
                           params={"query": f"{place_name} {address}", "display": 5},
                           headers=self.headers, timeout=10)
        if res.status_code != 200:
            logger.error(f"BlogContentLoader|지역검색 실패|{res.status_code}|{res.text[:200]}")
            return None

        for item in res.json().get("items", []):
            road = item.get("roadAddress") or ""
            if _nospace(address) not in _nospace(road):
                continue
            parts = road.split()
            name = re.sub(r"<[^>]+>", "", item["title"])
            hours = self.fetch_hours(name, road)
            return {
                "business_hours": json.dumps(hours, ensure_ascii=False) if hours else None,
                "business_days": open_days(hours),
                "break_time": json.dumps(sorted({tuple(b) for d in hours.values() if d for b in d["breaks"]}))
                              if hours else None,
                "name": name,
                "type": item.get("category"),
                "category": normalize_category(item.get("category")),
                "phone_number": item.get("telephone") or None,
                "location_detail": road,
                "location_province": parts[0] if parts else None,
                "location_city": parts[1] if len(parts) > 1 else None,
                "latitude": int(item["mapy"]) / 10_000_000,          # WGS84 x 1e7 정수로 내려옴
                "longitude": int(item["mapx"]) / 10_000_000,
                "crawled_at": datetime.date.today().isoformat(),
            }
        return None

    def fetch_hours(self, name, road_address):
        """네이버 모바일 지도 검색으로 플레이스 ID를 찾고, 플레이스 페이지에서 요일별 영업시간 수집. 실패하면 None."""
        # ponytail: 네이버 화면 내부 데이터(__RQ_STREAMING_STATE__, __APOLLO_STATE__) 구조에 의존. 개편되면 None만 나옴
        try:
            # 상세주소(층/호수)까지 넣으면 검색 결과가 비어서 "상호명 + 시/구"로 검색, 도로명+건물번호까지만 비교
            parts = road_address.split()
            road_base = _nospace(" ".join(parts[:4]))
            q = urllib.parse.quote(f"{name} {' '.join(parts[:2])}")
            res = requests.get(f"https://m.map.naver.com/search?query={q}&type=all&displayCount=5",
                               headers=MOBILE_UA, timeout=10)
            place_id = None
            for chunk in re.findall(r'window\.__RQ_STREAMING_STATE__\.push\((.*?)\);', res.content.decode("utf-8")):
                for query in json.loads(chunk).get("queries", []):
                    data = query.get("state", {}).get("data")
                    for it in (data.get("items") or []) if isinstance(data, dict) else []:
                        if _nospace(it.get("name", "")) == _nospace(name) or road_base in _nospace(it.get("roadAddress") or ""):
                            place_id = place_id or it["id"]
            if not place_id:
                return None
            time.sleep(0.3)     # 연속 요청 간격
            page = requests.get(f"https://m.place.naver.com/place/{place_id}/home", headers=MOBILE_UA, timeout=10)
            m = re.search(r'window\.__APOLLO_STATE__\s*=\s*(\{.*?\});', page.content.decode("utf-8"), re.S)
            if not m:
                return None
            root = json.loads(m.group(1)).get("ROOT_QUERY", {})
            detail = next((v for k, v in root.items() if k.startswith("placeDetail(") and isinstance(v, dict)), {})
            return parse_naver_hours(detail.get("newBusinessHours"))
        except Exception as e:
            logger.warning(f"BlogContentLoader|영업시간 수집 실패|{name}|{e}")
            return None

    def find_place_name(self, address):
        """주소로 네이버 통합검색 → 해당 주소에 있는 장소(상호명) 후보 목록 반환. 없으면 None."""
        # ponytail: 네이버 검색 화면 HTML 클래스(._5Dken)에 의존. 화면 개편되면 깨짐 → 후보가 계속 0이면 여기부터 확인
        encoding_address = urllib.parse.quote(address)
        url = f"https://search.naver.com/search.naver?ssc=tab.nx.all&query={encoding_address}"
        search_response = requests.get(url, timeout=10)

        if search_response.status_code == 200 :
            soup = BeautifulSoup(search_response.text,"html.parser")
            loc_main = soup.select_one("#loc-main-section-root")
            if loc_main:
                return loc_main.select("div ._5Dken")
        return None


if __name__=="__main__":
    BlogContentLoader().file_load()

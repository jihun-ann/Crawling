import json
import logging
import re
import urllib.parse
from os import access

import requests
from bs4 import BeautifulSoup
from scrapy.utils.project import get_project_settings
from pathlib import Path

from source.src.api.token import total_token

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

class BlogContentLoader:
    """크롤링된 블로그 JSON → 본문 속 주소/상호명 추출 → 네이버 지역검색으로 실제 장소 확인 → (예정) place DB 저장.

    실행: python -m source.src.sqlalchemy.services.blog_content_loader
    """
    def __init__(self):
        settings = get_project_settings()
        self.path = Path(settings.get("BASE_DIR"))/"source"/"src"/"blog_content"

    def file_load(self):
        """저장된 JSON을 하나씩 읽어 본문에서 도로명 주소를 정규식으로 찾고,
        주소별로 후보 상호명 중 본문에 가장 많이 언급된 이름을 장소로 판단해 retrive_place 호출.
        제외된 글(excluded_reason 있음)과 s_ 로 시작하는 파일은 건너뜀."""
        try:
            for dir in self.path.iterdir():
                content_dir = self.path/dir

                for file in content_dir.glob("*.json"):
                # for file in content_dir.glob("*223396237018.json"):
                    if not file.name.startswith("s_"):
                        with open(file, "r+", encoding="utf-8") as f:
                            file_data = json.load(f)
                            if file_data.get("excluded_reason"):
                                continue
                            #address_pattern = r'(?:[가-힣]+(?:시|도)\s)?[가-힣]+(?:구|군)\s[가-힣\d\s-]+(?:로|길)\s?[\d-]+'
                            SI_DO = r'(?:서울(?:특별시|시)|부산(?:광역시|시)|대구(?:광역시|시)|인천(?:광역시|시)|광주(?:광역시|시)|대전(?:광역시|시)|울산(?:광역시|시)|세종(?:특별자치시|시)|경기(?:도)|강원(?:특별자치도|도)|충북(?:도)|충청북도|충남(?:도)|충청남도|전북(?:도)|전라북도|전남(?:도)|전라남도|경북(?:도)|경상북도|경남(?:도)|경상남도|제주(?:특별자치도|도))'
                            SI_GUN_GU = r'[가-힣]+(?:시|군|구)'
                            ROAD = r'[가-힣\d]+(?:로|길)(?:[ \t]*\d+번?길)?'
                            BUILDING_INFO = r'\d{1,4}(?:-\d{1,4})?'
                            address_pattern = rf'(?:(?:{SI_DO}[ \t]+)?{SI_GUN_GU}[ \t]+){ROAD}[ \t]+{BUILDING_INFO}'

                            address = re.findall(address_pattern, file_data["context"])
                            if address:
                                idx = 0
                                first_address = ""
                                for add in address :
                                    if (first_address.replace(" ", "") in add.replace(" ", ""))or(add.replace(" ", "") in first_address.replace(" ", "")) :
                                        if first_address != "" : continue
                                    if first_address == "" : first_address = add

                                    print(file_data["filename"])
                                    sub_json = {}
                                    sub_place_list = self.find_place_name(add)
                                    print(sub_place_list)
                                    if not sub_place_list:
                                        logger.error(f"BlogContentLoader|sub place not found|sub_place_list is None|{file_data["title"]}|{add}")
                                        break
                                    for sub_place in sub_place_list:
                                        sub_place_name = sub_place.get_text()
                                        count = len(re.findall(re.escape(sub_place_name), file_data["context"]))
                                        if count != 0 : sub_json[sub_place_name] = count

                                    if sub_json:
                                        place_name = max(sub_json, key=sub_json.get)
                                        print(place_name)
                                        ignore_keyword = {"주차장","병원","유치원"}
                                        if any(k in place_name for k in ignore_keyword):
                                            continue
                                        self.retrive_place(place_name, add)
                                    else:
                                        continue
                                    idx += 1
                            #     print(file_data)
                            #     print(file_data["title"])
                            #     print(file_data["context"])
                            #     print(address)
        except Exception as e:
            logger.exception(f"BlogContentLoader|file_load Error|{e}")

    def retrive_place(self, place_name, address):
        """네이버 지역검색 API로 (상호명 + 주소) 검색. 결과가 1건이고 도로명 주소가 일치하면
        좌표(mapx/mapy)로 네이버 모바일 지도를 조회해 상세 정보를 찾음. (작업 중: 아직 저장/반환 없음)"""
        settings = get_project_settings()
        search_query = urllib.parse.quote(f"{place_name} {address}")
        url = f"https://openapi.naver.com/v1/search/local.xml?query={search_query}&display=5"
        headers = {"X-Naver-Client-Id": settings.get("NAVER_CLIENT_ID"),"X-Naver-Client-Secret": settings.get("NAVER_CLIENT_KEY")}
        search_response = requests.get(url, headers=headers)
        # print(search_response.text)

        if search_response.status_code == 200:
            soup = BeautifulSoup(search_response.text, "xml")
            place_items = soup.find_all("item")
            if place_items and len(place_items) == 1:
                for item in place_items:
                    print(str(address).replace(" ",""))
                    print(str(item.find("roadAddress").text).replace(" ",""))
                    if str(address).replace(" ","") in str(item.find("roadAddress").text).replace(" ",""):
                        encoding_address = urllib.parse.quote(f"{place_name} {address}")
                        mapx = int(item.find("mapx").get_text())/10000000
                        mapy = int(item.find("mapy").get_text())/10000000
                        mobaddress = f"https://m.map.naver.com/search?query={encoding_address}&type=all&searchCoord={mapx};{mapy}&displayCount=5"
                        print(mobaddress)
                        print("start")
                        mob_search_response = requests.get(mobaddress)

                        print(mob_search_response)
                        if mob_search_response.status_code == 200:
                            pattern = r'window\.__RQ_STREAMING_STATE__\.push\((.*?)\);'
                            matches = re.findall(pattern, mob_search_response.text)
                            for place_sub in matches:
                                matches_json = json.loads(place_sub)
                                for matche_item in matches_json["queries"]:
                                    sub_items_data = matche_item["state"]["data"]
                                    sub_items = sub_items_data.get("items")
                                    print(sub_items)
                                    if sub_items:
                                        for s_item in sub_items:
                                            if s_item["name"] == place_name:
                                                print(s_item)


                return None
            else:
                return None
        else:
            return None


        pass


    def find_place_name(self, address):
        """주소로 네이버 통합검색 → 해당 주소에 있는 장소(상호명) 후보 목록 반환. 없으면 None."""
        encoding_address = urllib.parse.quote(address)
        url = f"https://search.naver.com/search.naver?ssc=tab.nx.all&query={encoding_address}"
        search_response = requests.get(url)

        if search_response.status_code == 200 :
            soup = BeautifulSoup(search_response.text,"html.parser")
            loc_main = soup.select_one("#loc-main-section-root")
            if loc_main:
                sub_place_list = loc_main.select("div ._5Dken")
                return sub_place_list
            return None
        else :
            return None


if __name__=="__main__":
    loader = BlogContentLoader()
    loader.file_load()
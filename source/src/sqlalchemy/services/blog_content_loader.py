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
    def __init__(self):
        settings = get_project_settings()
        self.path = Path(settings.get("BASE_DIR"))/"source"/"src"/"blog_content"

    def file_load(self):
        try:
            for dir in self.path.iterdir():
                content_dir = self.path/dir

                for file in content_dir.glob("*.json"):
                # for file in content_dir.glob("*223396237018.json"):
                    if not file.name.startswith("s_"):
                        with open(file, "r+", encoding="utf-8") as f:
                            file_data = json.load(f)
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
                                    if not sub_place_list:
                                        logger.error(f"BlogContentLoader|sub place not found|sub_place_list is None|{file_data["title"]}|{add}")
                                        break
                                    for sub_place in sub_place_list:
                                        sub_place_name = sub_place.get_text()
                                        count = len(re.findall(re.escape(sub_place_name), file_data["context"]))
                                        if count != 0 : sub_json[sub_place_name] = count

                                    if sub_json:
                                        place_name = max(sub_json, key=sub_json.get)

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
        settings = get_project_settings()
        search_query = urllib.parse.quote(f"{place_name} {address}")
        url = f"https://openapi.naver.com/v1/search/local.xml?query={search_query}&display=5"
        headers = {"X-Naver-Client-Id": settings.get("NAVER_CLIENT_ID"),"X-Naver-Client-Secret": settings.get("NAVER_CLIENT_KEY")}
        search_response = requests.get(url, headers=headers)

        if search_response.status_code == 200:
            soup = BeautifulSoup(search_response.text, "xml")
            place_items = soup.find_all("item")
            if place_items and len(place_items) == 1:
                for item in place_items:
                    if address in item.find("roadAddress"):
                        "https://m.map.naver.com/search?query=%EC%88%9C%EC%A0%95%EB%B0%98%EC%A0%90%20%EC%84%9C%EC%9A%B8%ED%8A%B9%EB%B3%84%EC%8B%9C%20%EA%B0%95%EC%84%9C%EA%B5%AC%20%EA%B8%88%EB%82%AD%ED%99%94%EB%A1%9C%20103&type=all&searchCoord=126.8114612;37.5747343&displayCount=%205"
                        #여기로 조회해서 placeID 추출
                return None
            else:
                return None
        else:
            return None





    def find_place_name(self, address):
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
import urllib.request
import json
from scrapy import Spider
from importlib import resources
from collections import deque
from bs4 import BeautifulSoup

class NaverSpider(Spider):
    name = "naver_crawling"

    def start_requests(self):
        province = self.prov
        location_q = self.location_name(province)

        keyword_q = deque()
        keyword_q.append("맛집")
        #keyword_q = self.keyword_list()

        for location in location_q:
            for keyword in keyword_q:
                search_query = " ".join([location,keyword])
                self.searching_naver_blog(search_query)
                #self.searching_naver_blog(search_query)

    def searching_naver_blog(self, query):
        re_query = urllib.parse.quote(query)
        #url = "https://search.naver.com/search.naver?query=" + re_query                       #전체 통합 검색
        url = "https://search.naver.com/search.naver?ssc=tab.blog.all&query=" + re_query       #블로그 검색
        #url = "https://search.naver.com/search.naver?ssc=tab.cafe.all&query=" + re_query      #카페 검색

        request = urllib.request.Request(url)
        response = urllib.request.urlopen(request)
        rescode = response.getcode()
        if(rescode==200):
            response_body = response.read()
            self.parsing_html(response_body.decode('utf-8'))
        else:
            print("Error Code:" + rescode)

    def parsing_html(self,html):
        soup = BeautifulSoup(html,"html.parser")
        for span in soup.select("span.sds-comps-text-type-headline1"):
            text = span.get_text()
            if(text in ("경매", "법원경매", "부동산")) :
                continue
            else :
                a = span.find_parent("a")
                print(a.get("href"))
                pass

    def searching_naver_api_blog(self,query):
        client_id = "lBn2OlsTkSAo6Dyr6h1c"
        client_secret = "rFc99bozMu"
        re_query = urllib.parse.quote(query)

        url = "https://openapi.naver.com/v1/search/blog?query=" + re_query # JSON 결과
        #url = "https://openapi.naver.com/v1/search/blog.xml?query=" + encText # XML 결과
        request = urllib.request.Request(url)
        request.add_header("X-Naver-Client-Id",client_id)
        request.add_header("X-Naver-Client-Secret",client_secret)
        response = urllib.request.urlopen(request)
        rescode = response.getcode()
        if(rescode==200):
            response_body = response.read()
            print(query)
            print(response_body.decode('utf-8'))
        else:
            print("Error Code:" + rescode)

    def location_name(self, prov_value):
        q = deque()
        resource_path = resources.files("src.properties")
        # 지역명 JSON 추출
        with resource_path.joinpath("location_kr.json").open(encoding="utf-8") as f :
            locations = json.load(f)

        for province, cities in locations.items():
            if province == prov_value :
                if province in ("서울특별시", "인천시", "대전광역시", "세종특별시", "부산광역시"):
                    # 구 조회
                    for country, towns in cities.items() :
                        for town in towns :
                            location_name = " ".join([province, country, town])
                            q.append(location_name)
                else:
                    # 시 조회
                    for city, countries in cities.items() :
                        # 구 조회
                        for country, towns in countries.items():
                            # 동 조회
                            for town in towns:
                                location_name = " ".join([province, city, country, town])
                                q.append(location_name)

        return q


    def keyword_list(self):
        q = deque()
        resource_path = resources.files("src.properties")

        # 키워드 JSON 추출
        with resource_path.joinpath("keyword.json").open(encoding="utf-8") as f :
            keywords = json.load(f)

        for purpose, contents in keywords.items():
            for content in contents:
                q.append(content)

        return q
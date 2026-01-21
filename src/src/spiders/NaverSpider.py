import os
import sys
import urllib.request
import json
from scrapy import Spider
from importlib import resources
from collections import deque


class NaverSpider(Spider):
    name = "naver_crawling"

    def start_requests(self):
        location_q = self.location_name(self.prov)
        keyword_q = self.keyword_list()
        for location in location_q:
            for keyword in keyword_q:
                search_query = " ".join([location,keyword])
                self.searching_naver_map(search_query)
                #self.searching_naver_blog(search_query)

    def searching_naver_map(self, query):
        re_query = query.replace(" ","+")
        print(re_query)
        url = "https://map.naver.com/search/" + re_query
        print(url)
        request = urllib.request.Request(url)
        response = urllib.request.urlopen(request)
        rescode = response.getcode()
        if(rescode==200):
            response_body = response.read()
            print(query)
            print(response_body.decode('utf-8'))
        else:
            print("Error Code:" + rescode)

    def searching_naver_blog(self,query):
        client_id = "lBn2OlsTkSAo6Dyr6h1c"
        client_secret = "rFc99bozMu"
        encText = urllib.parse.quote(query)

        url = "https://openapi.naver.com/v1/search/blog?query=" + encText # JSON 결과
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
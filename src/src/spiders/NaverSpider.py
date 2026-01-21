import scrapy
import json
from scrapy import Spider
from importlib import resources


class NaverSpider(Spider):
    name = "naver_crawling"

    def start_requests(self):
        url = "https://map.naver.com"
        with resources.files("src.properties").joinpath("location_kr.json").open(encoding="utf-8") as f:
            locations = json.load(f)
        print("??" + self.prov)

        for province, cities in locations.items():
            print(province)
            if province in ("서울특별시", "인천시", "대전광역시", "세종특별시", "부산광역시"):
                for countries in cities.items() :
                    print(countries)
            else:
                for city in cities.items() :
                    print(city)
        yield scrapy.Request(url, self.parse_province_list)

    def parse_city_list(self, response):
        pass
    #     location_province = scrapy.Field()      #도
    # location_city = scrapy.Field()          #시
    # location_country = scrapy.Field()       #구
    # location_town = scrapy.Field()          #동
    # location_detail = scrapy.Field()        #상세주소
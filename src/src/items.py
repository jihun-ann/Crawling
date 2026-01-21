
import scrapy


class SrcItem(scrapy.Item):
    # 장소 정보
    place_id = scrapy.Field()
    name = scrapy.Field()                   #상호명
    type = scrapy.Field()                   #업종
    phone_number = scrapy.Field()           #전화번호
    business_hours = scrapy.Field()         #영업시간
    business_days = scrapy.Field()          #영업요일
    break_time = scrapy.Field()             #브레이크타임
    business_status = scrapy.Field()        #영업여부
    image_urls = scrapy.Field()                 #대표이미지URL [url1,url2,url3]

    review_count_platform = scrapy.Field()  #검색 플랫폼 전용 리뷰수
    review_count_blog = scrapy.Field()      #블로그 전용 리뷰수
    visit_rate = scrapy.Field()             #방문율
    rating = scrapy.Field()                 #평점
    price_level = scrapy.Field()            #비용 레벨 / 1~5

    keywords = scrapy.Field()               #키워드 ["데이트", "혼밥", "분위기좋은"]
    visit_purpose = scrapy.Field()          #방문목적 ["데이트", "회식", "혼밥"]
    blog_review_urls = scrapy.Field()       #인기 블로그URL [url1, url2, url3] 조회수>최근
    blog_review_count = scrapy.Field()      #최근 30일 블로그 리뷰 수

    # 위치 정보
    location_zipcode = scrapy.Field()       #우편번호
    location_province = scrapy.Field()      #도
    location_city = scrapy.Field()          #시, 군
    location_country = scrapy.Field()       #구, 면
    location_town = scrapy.Field()          #동, 리
    location_detail = scrapy.Field()        #상세주소

    latitude = scrapy.Field()               #위도
    longitude = scrapy.Field()              #경도

    crawled_at = scrapy.Field()             #크롤링 일자

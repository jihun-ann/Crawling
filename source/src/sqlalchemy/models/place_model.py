from source.src.sqlalchemy.database import Base
from sqlalchemy import Column, Integer, String

class Place(Base):
    __tablename__ = "place"
    # 장소 정보
    place_id = Column(Integer, primary_key=True)
    name = Column(String)                          #상호명
    type = Column(String)                          #업종
    phone_number = Column(String)                  #전화번호
    business_hours = Column(String)                #영업시간
    business_days = Column(String)                 #영업요일
    break_time = Column(String)                    #브레이크타임
    business_status = Column(String)               #영업여부
    image_urls = Column(String)                    #대표이미지URL [url1,url2,url3]

    review_count_platform = Column(Integer, default=0)         #검색 플랫폼 전용 리뷰수
    review_count_blog = Column(Integer, default=0)             #블로그 전용 리뷰수
    visit_rate = Column(Integer, default=0)                    #방문율
    rating = Column(Integer, default=0)                        #평점
    price_level = Column(Integer, default=0)                   #비용 레벨 / 1~5

    keywords = Column(String)                      #키워드 ["데이트", "혼밥", "분위기좋은"]
    visit_purpose = Column(String)                 #방문목적 ["데이트", "회식", "혼밥"]
    blog_review_urls = Column(String)              #인기 블로그URL [url1, url2, url3] 조회수>최근
    blog_review_count = Column(Integer, default=0)             #최근 30일 블로그 리뷰 수

    # 위치 정보
    location_zipcode = Column(Integer)             #우편번호
    location_province = Column(String)             #도
    location_city = Column(String)                 #시, 군
    location_country = Column(String)              #구, 면
    location_town = Column(String)                 #동, 리
    location_detail = Column(String)               #상세주소

    latitude = Column(String)                      #위도
    longitude = Column(String)                     #경도

    crawled_at = Column(String)                    #크롤링 일자
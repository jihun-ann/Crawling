from source.src.sqlalchemy.database import Base
from sqlalchemy import Column, Integer, String, Float, Boolean, Date, ForeignKey, Sequence

class Place(Base):
    """추천 대상 장소 (카페, 맛집, 관광지 등). 블로그 크롤링 결과로 채워짐."""
    __tablename__ = "place"
    # 장소 정보
    place_id = Column(Integer, Sequence("seq_place"), primary_key=True)
    name = Column(String)                          #상호명
    type = Column(String)                          #업종 원문 (네이버 카테고리, 예: 카페,디저트)
    category = Column(String)                      #정규화 업종: 카페/맛집/소품샵/관광지/숙소/기타
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

    latitude = Column(Float)                       #위도
    longitude = Column(Float)                      #경도

    # 추천 점수 (place_crud.update_scores에서 계산)
    score = Column(Float, default=0)               #언급 수 + 최근 언급 수 - 부정 비율
    negative_ratio = Column(Float, default=0)      #부정 후기 비율 (높으면 '생각보다 별로'로 제외)

    crawled_at = Column(String)                    #크롤링 일자


class PlaceReview(Base):
    """장소 ↔ 후기 글 연결. 한 글이 여러 장소를, 한 장소가 여러 글을 가질 수 있음."""
    __tablename__ = "place_review"
    place_id = Column(Integer, ForeignKey("place.place_id", ondelete="CASCADE"), primary_key=True)
    content_id = Column(String, primary_key=True)  #글 ID (blog_content JSON 파일명)
    platform = Column(String)
    url = Column(String)
    title = Column(String)
    posted_at = Column(Date)                       #글 작성일
    is_negative = Column(Boolean, default=False)   #부정 후기 여부
    moods = Column(String)                         #분위기 태그 JSON ["조용한", ...]

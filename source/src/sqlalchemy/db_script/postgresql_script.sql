--PLACE Table Create
create table place(
	place_id INTEGER PRIMARY KEY,

    name VARCHAR,
    type VARCHAR,
    phone_number VARCHAR,
    business_hours VARCHAR,
    business_days VARCHAR,
    break_time VARCHAR,
    business_status VARCHAR,
    image_urls VARCHAR,

    review_count_platform INTEGER DEFAULT 0,
    review_count_blog INTEGER DEFAULT 0,
    visit_rate INTEGER DEFAULT 0,
    rating INTEGER DEFAULT 0,
    price_level INTEGER DEFAULT 0,

    keywords TEXT,
    visit_purpose TEXT,
    blog_review_urls TEXT,
    blog_review_count INTEGER DEFAULT 0,

    location_zipcode INTEGER,
    location_province VARCHAR,
    location_city VARCHAR,
    location_country VARCHAR,
    location_town VARCHAR,
    location_detail VARCHAR,

    latitude VARCHAR,
    longitude VARCHAR,

    crawled_at VARCHAR
);

CREATE SEQUENCE seq_place START 1;


-- Test PLACE DATA Create
INSERT INTO public.place
(place_id, "name", "type", phone_number, business_hours, business_days, break_time, business_status, image_urls, review_count_platform, review_count_blog, visit_rate, rating, price_level, keywords, visit_purpose, blog_review_urls, blog_review_count, location_zipcode, location_province, location_city, location_country, location_town, location_detail, latitude, longitude, crawled_at)
VALUES(1, 'TEST', '식당', '01012341234', '09:00~22:00', '["월","화","수","목","금"]', '14:00~15:00', '1', 'naver.com', 0, 0, 0, 0, 0, '["데이트"]', '["데이트"]', 'naver.com', 0, 0, '도', '시', '구', '동', '상세', '위도', '경도', '2026-02-06');
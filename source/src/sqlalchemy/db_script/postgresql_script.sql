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
    blog_review_count INTEGER,

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
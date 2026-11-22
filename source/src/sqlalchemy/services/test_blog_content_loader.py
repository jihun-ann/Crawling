# 장소 매칭 로직 자체 검사 (네트워크/DB 불필요). 실행: python -m source.src.sqlalchemy.services.test_blog_content_loader
from source.src.sqlalchemy.services.blog_content_loader import BlogContentLoader, _nospace


def make_loader(places):
    loader = BlogContentLoader.__new__(BlogContentLoader)    # __init__(DB 연결) 생략
    loader.places = [(pid, _nospace(name), _nospace(road)) for pid, name, road in places]
    return loader


if __name__ == "__main__":
    L = make_loader([
        (1, "에버랜드", "경기도 용인시 처인구 포곡읍 에버랜드로 199"),
        (2, "공항동", "서울특별시 강서구 방화대로7나길 39 101호"),          # 동네 이름과 같은 상호
        (3, "카페 툇마루", "강원특별자치도 강릉시 난설헌로 232"),
        (4, "순정반점 방화점", "서울특별시 강서구 금낭화로 103 1층"),
        (5, "중화루", "서울특별시 강서구 금낭화로 103 2층"),                 # 같은 건물 다른 가게
    ])

    # 상호명 매칭: 검색어 지역 안 + 이름이 본문에 있을 때만
    assert L.known_places_named("에버랜드 다녀왔어요", "용인 에버랜드 후기") == {1}
    assert L.known_places_named("에버랜드 다녀왔어요", "강릉 카페") == set()           # 지역 불일치
    assert L.known_places_named("에버랜드 다녀왔어요", None) == set()                  # 지역 힌트 없음
    assert L.known_places_named("카페툇마루 최고", "강릉 카페") == {3}                 # 띄어쓰기 무시
    assert L.known_places_named("공항동 살아요", "서울특별시 강서구 방화동 맛집") == set()  # 동네 이름형 상호 제외

    # 주소 캐시: 같은 주소 + 이름이 본문에 있는 기존 장소 재사용, 같은 건물이면 더 많이 언급된 곳
    text = "강서구 금낭화로 103 순정반점 방화점 짜장면, 순정반점 방화점 또 갈게요. 위층 중화루"
    assert L.known_place_at("강서구 금낭화로 103", text) == 4
    assert L.known_place_at("강서구 금낭화로 999", text) is None
    assert L.known_place_at("강서구 방화대로7나길 39", "공항동 고기 맛있음") == 2      # 주소로 확인되면 연결

    # 본문 속 주소 추출: 같은 주소 다른 표기는 하나로
    assert L.unique_addresses("서울특별시 강서구 금낭화로 103 / 강서구 금낭화로 103") == ["서울특별시 강서구 금낭화로 103"]
    print("ok")

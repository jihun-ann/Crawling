# place 테이블 조회/저장 함수 (API, 로더에서 사용)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
import logging

from source.src.sqlalchemy.models.place_model import Place
from sqlalchemy import Column, Integer, String, update

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def get_place_all_list(db: Session):
    """전체 장소 목록."""
    return db.query(Place).all()

def get_place_id(db: Session, place_id: Integer):
    """place_id로 장소 1건 조회. 없으면 None."""
    return db.query(Place).filter_by(place_id = place_id).first()

def upsert_place(db: Session, new_place: Place):
    """place_id 기준으로 없으면 추가, 있으면 값 갱신. 성공 여부(bool) 반환."""
    result = False
    retrieve_place = db.query(Place).filter_by(place_id = new_place.place_id).first()

    try:
        #신규
        if not retrieve_place:
                db.add(new_place)

        #변경
        else :
            for key, value in vars(new_place).items():
                if not key.startswith('_') and key != 'place_id':
                    setattr(retrieve_place, key, value)

        db.commit()
        result = True
    except SQLAlchemyError  as e:
        db.rollback()
        logger.exception(f"place_crud|upsert_place|Create Transaction Error|{e}")

    return result

def save_place(db: Session, place: dict):
    """장소 저장. (상호명, 도로명주소)가 같으면 기본 정보만 갱신. place_id 반환."""
    from sqlalchemy.dialects.postgresql import insert
    stmt = insert(Place).values(**place)
    stmt = stmt.on_conflict_do_update(
        index_elements=["name", "location_detail"],
        set_={k: stmt.excluded[k] for k in place if k not in ("name", "location_detail")},
    ).returning(Place.place_id)
    place_id = db.execute(stmt).scalar()
    db.commit()
    return place_id


def add_review(db: Session, review: dict):
    """장소-글 연결 저장. 이미 있으면 무시."""
    from sqlalchemy.dialects.postgresql import insert
    from source.src.sqlalchemy.models.place_model import PlaceReview
    db.execute(insert(PlaceReview).values(**review).on_conflict_do_nothing())
    db.commit()


# 점수 = ln(1+전체 언급) + 0.5*ln(1+최근 30일 언급) - 2*부정 비율
SCORE_SQL = """
UPDATE place p SET
    review_count_blog = s.cnt,
    blog_review_count = s.recent,
    negative_ratio = s.neg,
    score = ln(1 + s.cnt) + 0.5 * ln(1 + s.recent) - 2 * s.neg,
    blog_review_urls = s.urls,
    keywords = s.moods
FROM (
    SELECT place_id,
           count(*) AS cnt,
           count(*) FILTER (WHERE posted_at >= current_date - 30) AS recent,
           avg(is_negative::int) AS neg,
           (array_to_json((array_agg(url ORDER BY posted_at DESC NULLS LAST))[1:3]))::text AS urls,
           (SELECT json_agg(m ORDER BY m)::text FROM (
                SELECT DISTINCT json_array_elements_text(r2.moods::json) AS m
                FROM place_review r2 WHERE r2.place_id = r.place_id AND r2.moods IS NOT NULL) t) AS moods
    FROM place_review r
    GROUP BY place_id
) s
WHERE p.place_id = s.place_id
"""


def update_scores(db: Session):
    """place_review 기준으로 언급 수 / 최근 30일 언급 수 / 부정 비율 / 점수 / 분위기 태그 / 대표 후기 URL 갱신."""
    from sqlalchemy import text
    n = db.execute(text(SCORE_SQL)).rowcount
    db.commit()
    return n

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
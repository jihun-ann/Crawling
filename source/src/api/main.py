from fastapi import FastAPI, Depends
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from sqlalchemy.orm import Session
import logging

from source.src.spiders.NaverSpider import NaverSpider
from source.src.sqlalchemy.models.place_model import Place
from source.src.sqlalchemy.crud import place_crud
from source.src.sqlalchemy import database

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)
app = FastAPI()

def get_db():
    db_session = database.SessionLocal()
    try:
        yield db_session
    finally:
        db_session.close()

@app.get("/test")
def test():
    settings = get_project_settings()

    try:
        spider_process = CrawlerProcess(settings)
        spider_process.crawl(NaverSpider,prov="서울특별시")
        # spider_process.start()
        return {"code":200}
    except Exception as e:
        logger.error(f"Crawling API Error {e}")
        return {"code":400}


@app.get("/test2")
def get_place(db: Session = Depends(get_db)):
    place_db = place_crud
    place = place_db.get_place_id(db,1)
    return {"code":200, "response":place}


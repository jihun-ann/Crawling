from scrapy.utils.project import get_project_settings
import requests
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

def get_sgis_access_token():
    try:
        settings = get_project_settings()
        client_param = {"consumer_key":f"{settings.get("SGIS_CLIENT_ID")}","consumer_secret":f"{settings.get("SGIS_CLIENT_KEY")}"}
        token_url = "https://sgisapi.mods.go.kr/OpenAPI3/auth/authentication.json"
        token_response = requests.get(token_url,params=client_param)

        if token_response.status_code == 200:
            access_token_json = token_response.json()
            access_token = access_token_json["result"]["accessToken"]
            return access_token
        else : return None

    except Exception as e:
        logger.exception(f"TotalToken.py|get_sgis_access_token Method Error|{e}")

def get_ncloud_access_token():
    try:
        settings = get_project_settings()
        client_param = {"consumer_key":f"{settings.get("NCLOUD_CLIENT_ID")}","consumer_secret":f"{settings.get("NCLOUD_CLIENT_KEY")}"}
        token_url = "https://sgisapi.mods.go.kr/OpenAPI3/auth/authentication.json"
        token_response = requests.get(token_url,params=client_param)

        if token_response.status_code == 200:
            access_token_json = token_response.json()
            access_token = access_token_json["result"]["accessToken"]
            return access_token
        else : return None
    except Exception as e:
        logger.exception(f"TotalToken.py|get_ncloud_access_token Method Error|{e}")

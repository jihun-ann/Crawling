"""글 ID 정규화 / 중복 해시 / 광고·AI글 판별 (룰 기반)."""
import datetime
import hashlib
import re
from urllib.parse import urlparse, parse_qs


def content_id(url):
    """같은 글이면 URL 형태(m., PostView, 쿼리)와 무관하게 같은 ID. 기존 파일명 규칙과 호환."""
    u = urlparse(url)
    host = u.netloc.removeprefix("m.")
    q = {k: v[0] for k, v in parse_qs(u.query).items()}
    parts = [p for p in u.path.split("/") if p]

    if host == "blog.naver.com":
        blog_id = q.get("blogId") or (parts[0] if parts and not parts[0].endswith(".naver") else None)
        log_no = q.get("logNo") or (parts[1] if len(parts) > 1 else None)
        if blog_id and log_no:
            return f"blog.naver.com_{blog_id}_{log_no}"
    if host in ("youtube.com", "www.youtube.com", "youtu.be"):
        video = q.get("v") or (parts[-1] if parts else None)
        if video:
            return f"youtube.com_{video}"
    if host == "cafe.naver.com":
        if q.get("clubid") and q.get("articleid"):
            return f"cafe.naver.com_{q['clubid']}_{q['articleid']}"
        if len(parts) >= 2:
            return f"cafe.naver.com_{parts[0]}_{parts[1]}"
    return (host + u.path).rstrip("/").replace("/", "_")


def parse_post_date(text, today=None):
    """글 작성일 문자열 → 'YYYY-MM-DD'. '2025. 8. 20. 14:31', '2025-08-20', '3시간 전', '2일 전' 지원. 모르면 None."""
    today = today or datetime.date.today()
    text = text or ""
    m = re.search(r"(\d{4})\s*[.\-/]\s*(\d{1,2})\s*[.\-/]\s*(\d{1,2})", text)
    if m:
        return datetime.date(*map(int, m.groups())).isoformat()
    if re.search(r"\d+\s*(분|시간)\s*전|방금", text):
        return today.isoformat()
    m = re.search(r"(\d+)\s*일\s*전", text)
    if m:
        return (today - datetime.timedelta(days=int(m.group(1)))).isoformat()
    return None


def content_hash(text):
    """공백 무시 본문 해시. 다른 URL로 퍼간 동일 본문 잡기용."""
    # ponytail: 완전 동일 본문만 잡음. 일부 수정된 복붙까지 잡으려면 simhash/minhash로 교체
    return hashlib.sha1(re.sub(r"\s+", "", text or "").encode("utf-8")).hexdigest()


# 광고: 공정위 표기 문구 / 체험단 플랫폼명 / 업체가 퍼온 후기
AD_PHRASES = ("원고료", "제공받", "제공 받", "무상으로 제공", "지원받아", "지원 받아", "체험단", "서포터즈",
              "업체로부터", "대가성", "공정거래위원회", "유료광고", "유료 광고", "파트너스 활동", "수수료를 제공",
              "레뷰", "리뷰노트", "디너의여왕", "링블")
AD_SPONSOR = re.compile(r"(?<!노)협찬(?!\s*(?:아님|아니|아닌|[xX×✕]|없|0))")
AD_REPOST = re.compile(r"출처\s*[:：]?.{0,40}blog\.naver\.com")

# AI글: 템플릿 문구 많고 경험 흔적이 없으면 AI로 판단
AI_PHRASES = ("알아보겠습니다", "알아보도록", "살펴보겠습니다", "소개해 드리겠습니다", "결론적으로", "요약하자면",
              "도움이 되셨", "도움이 되길", "도움이 되었으면", "이상으로", "잊지 못할", "특별한 경험", "완벽한 선택",
              "만족스러운 경험", "뿐만 아니라", "마무리하며", "한마디로", "누구나 만족", "강력 추천")
AI_MARKDOWN = re.compile(r"\*\*[^*\n]+\*\*|^#{1,3}\s", re.M)
HUMAN_TRACE = re.compile(r"ㅋㅋ|ㅎㅎ|ㅠㅠ|ㅜㅜ|\^\^|내돈내산|재방문|웨이팅|먹었|다녀왔|갔는데|갔다|시켰|주문했|남편|와이프|친구랑|아이랑")
AI_MIN_HITS = 3     # 튜닝 포인트: 오탐 많으면 올리기


# 부정 후기: 이 표현이 NEGATIVE_MIN_HITS개 이상이면 부정 글로 봄
# ponytail: 글 전체 기준 키워드 판정. 한 글에 여러 장소가 있으면 장소별 구분 못 함 → 필요 시 장소명 주변 문장만 보기
NEGATIVE = re.compile(r"별로|실망|비추|최악|불친절|맛없|다신\s*안|다시는\s*안|재방문\s*(의사\s*)?(없|X|x)|아쉬웠|돈\s*아깝|비싸기만")
NEGATIVE_MIN_HITS = 2

# 분위기 태그 (웹 MOODS와 같은 이름)
MOOD_WORDS = {
    "조용한": ("조용", "한적", "아늑", "여유롭", "힐링"),
    "할 게 많은": ("체험", "볼거리", "놀거리", "액티비티", "즐길거리", "구경거리"),
    "자연": ("바다", "오션뷰", "산책", "숲", "호수", "계곡", "자연"),
    "감성/사진": ("감성", "포토존", "인스타", "사진 맛집", "예쁜", "분위기 좋"),
}


# 네이버 업종 문자열(예: "카페,디저트", "음식점>한식") → 코스 단계용 업종. 위에서부터 먼저 맞는 것
CATEGORY_RULES = (
    ("숙소", ("숙박", "호텔", "펜션", "모텔", "리조트", "게스트하우스", "민박", "캠핑")),
    ("카페", ("카페", "디저트", "베이커리", "제과", "커피", "찻집", "빙수")),
    ("소품샵", ("소품", "잡화", "기념품", "문구", "생활용품", "편집샵", "공방")),
    # "스파,"(쉼표 포함): 네이버 업종 "스파,온천"만 잡고 "스파게티"는 제외
    ("테마파크", ("테마파크", "놀이공원", "워터파크", "스파,", "온천", "아쿠아리움", "동물원", "눈썰매장", "키즈파크")),
    ("관광지", ("여행", "명소", "관광", "공원", "해수욕장", "박물관", "미술관", "전시", "계곡", "사찰", "유적", "체험")),
    ("맛집", ("음식점", "한식", "중식", "일식", "양식", "분식", "고기", "육류", "해물", "횟집", "치킨", "술집", "요리",
             "식당", "뷔페", "국수", "냉면", "찌개", "국밥", "샤브샤브")),
)


def normalize_category(naver_category):
    text = naver_category or ""
    return next((cat for cat, words in CATEGORY_RULES if any(w in text for w in words)), "기타")


def is_negative(text):
    return len(NEGATIVE.findall(text or "")) >= NEGATIVE_MIN_HITS


def mood_tags(text):
    text = text or ""
    return [mood for mood, words in MOOD_WORDS.items() if any(w in text for w in words)]


def exclude_reason(title, text):
    """제외 사유 문자열, 통과면 None."""
    body = f"{title or ''}\n{text or ''}"

    hit = next((p for p in AD_PHRASES if p in body), None)
    if hit:
        return f"ad:{hit}"
    if AD_SPONSOR.search(body):
        return "ad:협찬"
    if AD_REPOST.search(body):
        return "ad:repost"

    # 룰 기반이라 노골적인 AI글만 걸림 → 애매한 글(is_borderline)은 llm_check로 2차 판정
    ai_hits, human_hits = _ai_signals(body)
    if ai_hits >= AI_MIN_HITS and human_hits == 0:
        return f"ai:{ai_hits}"
    return None


def _ai_signals(body):
    return (sum(p in body for p in AI_PHRASES) + (2 if AI_MARKDOWN.search(body) else 0),
            len(HUMAN_TRACE.findall(body)))


def is_borderline(title, text):
    """룰은 통과했지만 AI 템플릿 문구가 하나라도 있는 글 → LLM 2차 판정 대상."""
    return _ai_signals(f"{title or ''}\n{text or ''}")[0] >= 1


if __name__ == "__main__":
    ids = {content_id(u) for u in (
        "https://blog.naver.com/abc/223978309252",
        "https://m.blog.naver.com/abc/223978309252?referrerCode=0",
        "https://blog.naver.com/PostView.naver?blogId=abc&logNo=223978309252&redirect=Dlog",
    )}
    assert ids == {"blog.naver.com_abc_223978309252"}, ids
    assert content_id("https://cafe.naver.com/joonggonara/123?art=x") == "cafe.naver.com_joonggonara_123"
    assert content_id("https://www.youtube.com/watch?v=abc123") == content_id("https://youtu.be/abc123") == "youtube.com_abc123"
    assert content_id("https://foo.tistory.com/123") == "foo.tistory.com_123"
    assert content_hash("a b\nc") == content_hash("abc")
    d0 = datetime.date(2026, 11, 22)
    assert parse_post_date("2025. 8. 20. 14:31", d0) == "2025-08-20"
    assert parse_post_date("3시간 전", d0) == "2026-11-22"
    assert parse_post_date("2일 전", d0) == "2026-11-20"
    assert parse_post_date("", d0) is None

    assert exclude_reason("맛집", "본 포스팅은 소정의 원고료를 받아 작성") == "ad:원고료"
    assert exclude_reason("맛집", "협찬 받아 다녀왔어요") == "ad:협찬"
    assert exclude_reason("맛집", "노협찬 내돈내산 후기, 협찬 아님 ㅎㅎ") is None
    assert exclude_reason("맛집", "글, 사진 출처: 개폼슛님의 블로그(https://blog.naver.com/x/1)") == "ad:repost"
    ai = "오늘은 이곳을 알아보겠습니다. **분위기** 뿐만 아니라 특별한 경험. 결론적으로 강력 추천"
    assert exclude_reason("맛집", ai).startswith("ai:")
    assert exclude_reason("맛집", ai + " 웨이팅 30분 하고 먹었는데 ㅋㅋ") is None
    assert normalize_category("카페,디저트") == "카페"
    assert normalize_category("음식점>한식>육류,고기요리") == "맛집"
    assert normalize_category("여행,명소>해수욕장") == "관광지"
    assert normalize_category("주차장") == "기타"
    assert normalize_category("테마파크") == normalize_category("스파,온천") == "테마파크"
    assert normalize_category("양식>스파게티,파스타전문") == "맛집"
    assert is_negative("기대했는데 실망. 직원도 불친절")
    assert not is_negative("맛있어요! 별로 안 기다렸어요")
    assert mood_tags("조용하고 오션뷰가 예쁜 곳") == ["조용한", "자연", "감성/사진"]
    print("ok")

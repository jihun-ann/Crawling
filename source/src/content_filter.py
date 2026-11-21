"""글 ID 정규화 / 중복 해시 / 광고·AI글 판별 (룰 기반)."""
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
    if host == "cafe.naver.com":
        if q.get("clubid") and q.get("articleid"):
            return f"cafe.naver.com_{q['clubid']}_{q['articleid']}"
        if len(parts) >= 2:
            return f"cafe.naver.com_{parts[0]}_{parts[1]}"
    return (host + u.path).rstrip("/").replace("/", "_")


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

    # ponytail: 룰 기반이라 노골적인 AI글만 걸림. 정밀도 필요하면 애매한 글만 LLM 분류기로 2차 판정
    ai_hits = sum(p in body for p in AI_PHRASES) + (2 if AI_MARKDOWN.search(body) else 0)
    human_hits = len(HUMAN_TRACE.findall(body))
    if ai_hits >= AI_MIN_HITS and human_hits == 0:
        return f"ai:{ai_hits}"
    return None


if __name__ == "__main__":
    ids = {content_id(u) for u in (
        "https://blog.naver.com/abc/223978309252",
        "https://m.blog.naver.com/abc/223978309252?referrerCode=0",
        "https://blog.naver.com/PostView.naver?blogId=abc&logNo=223978309252&redirect=Dlog",
    )}
    assert ids == {"blog.naver.com_abc_223978309252"}, ids
    assert content_id("https://cafe.naver.com/joonggonara/123?art=x") == "cafe.naver.com_joonggonara_123"
    assert content_hash("a b\nc") == content_hash("abc")

    assert exclude_reason("맛집", "본 포스팅은 소정의 원고료를 받아 작성") == "ad:원고료"
    assert exclude_reason("맛집", "협찬 받아 다녀왔어요") == "ad:협찬"
    assert exclude_reason("맛집", "노협찬 내돈내산 후기, 협찬 아님 ㅎㅎ") is None
    assert exclude_reason("맛집", "글, 사진 출처: 개폼슛님의 블로그(https://blog.naver.com/x/1)") == "ad:repost"
    ai = "오늘은 이곳을 알아보겠습니다. **분위기** 뿐만 아니라 특별한 경험. 결론적으로 강력 추천"
    assert exclude_reason("맛집", ai).startswith("ai:")
    assert exclude_reason("맛집", ai + " 웨이팅 30분 하고 먹었는데 ㅋㅋ") is None
    print("ok")

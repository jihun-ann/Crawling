# 광고/AI글 2차 판정 (Claude). 룰 기반(content_filter)으로 애매한 글만 pipelines에서 호출
# 켜기: .env 에 AI_CHECK_WITH_LLM=1 + ANTHROPIC_API_KEY (또는 `ant auth login`)
import json
import logging

import anthropic

logger = logging.getLogger(__name__)

MODEL = "claude-opus-5-5"   # 비용을 줄이려면 claude-haiku-5-5 로 변경 가능 (분류 작업이라 품질 차이 작음)

PROMPT = """다음은 여행/맛집 후기로 수집된 한국어 블로그 글입니다. 두 가지를 판정해 주세요.
- ai_written: 실제 방문 경험 없이 AI로 생성했거나 정보만 짜깁기한 글이면 true.
  (구체적인 개인 경험·감정·사소한 디테일·사진 설명이 있으면 사람 글일 가능성이 높음)
- sponsored: 협찬·체험단·원고료 등 대가를 받은 광고 글이거나 업체가 직접 쓴 홍보 글이면 true.
reason에는 판단 근거를 한 문장으로 적어 주세요.

<title>{title}</title>
<content>
{content}
</content>"""

SCHEMA = {
    "type": "object",
    "properties": {
        "ai_written": {"type": "boolean"},
        "sponsored": {"type": "boolean"},
        "reason": {"type": "string"},
    },
    "required": ["ai_written", "sponsored", "reason"],
    "additionalProperties": False,
}

_client = None


def llm_verdict(title, text):
    """{"ai_written", "sponsored", "reason"} 반환. 오류/거절 시 None (크롤링은 계속 진행)."""
    global _client
    _client = _client or anthropic.Anthropic()
    try:
        response = _client.beta.messages.create(
            model=MODEL,
            max_tokens=1024,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",                       # 안전 분류기가 거절하면 다른 모델로 자동 재시도
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
            messages=[{"role": "user", "content": PROMPT.format(title=title or "", content=text or "")}],
        )
    except anthropic.RateLimitError:
        logger.warning("LLM 판정|요청 한도 초과, 건너뜀")
        return None
    except anthropic.APIStatusError as e:
        logger.warning(f"LLM 판정|API 오류 {e.status_code}|{e.message}")
        return None
    except anthropic.APIConnectionError:
        logger.warning("LLM 판정|연결 실패, 건너뜀")
        return None

    if response.stop_reason == "refusal":
        return None
    text_block = next((b.text for b in response.content if b.type == "text"), None)
    return json.loads(text_block) if text_block else None

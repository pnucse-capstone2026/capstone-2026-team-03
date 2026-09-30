import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings


class QwenFeedbackError(Exception):
    pass


def generate_feedback(*, sentence, target_ipa, recognized_ipa, score, errors):
    """Request concise Korean pronunciation guidance from the local Qwen server."""
    prompt = {
        "sentence": sentence,
        "target_ipa": target_ipa,
        "recognized_ipa": recognized_ipa,
        "score": float(score),
        "errors": [
            {
                "sequence": error["sequence"],
                "word": error["word"],
                "target_phone": error["target_phone"],
                "recognized_phone": error["recognized_phone"],
                "operation": error["operation"],
            }
            for error in errors
        ],
    }
    payload = {
        "model": settings.QWEN_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "당신은 한국어 발음 교정 전문가입니다. 제공된 IPA 정렬 결과만 근거로 "
                    "간결하고 격려하는 한국어 피드백을 작성하세요. 진단이나 치료를 약속하지 마세요. "
                    "반드시 JSON만 출력하세요. 형식은 "
                    '{"summary":"500자 이하","content":"2000자 이하",'
                    '"priority_items":["50자 이하", "..."],'
                    '"error_feedback":[{"sequence":0,"summary":"...",'
                    '"content":"...","practice_tip":"..."}]} 입니다. '
                    "priority_items는 최대 3개, error_feedback은 주어진 오류 sequence만 사용하세요."
                ),
            },
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
        ],
        "temperature": 0.3,
        "max_tokens": 900,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    request = Request(
        f"{settings.QWEN_BASE_URL.rstrip('/')}/v1/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=settings.QWEN_TIMEOUT_SECONDS) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
        content = response_payload["choices"][0]["message"]["content"]
        feedback = _parse_feedback(content, {error["sequence"] for error in errors})
    except (HTTPError, URLError, TimeoutError, KeyError, IndexError, TypeError, json.JSONDecodeError, ValueError) as exc:
        raise QwenFeedbackError("Qwen 교정 피드백 생성에 실패했습니다.") from exc

    feedback.update(
        {
            "model_name": settings.QWEN_MODEL,
            "model_version": "Qwen3-8B-AWQ",
            "is_validated": True,
        }
    )
    return feedback


def _parse_feedback(content, error_sequences):
    if not isinstance(content, str):
        raise ValueError("Qwen content is not a string")
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    if not text.startswith("{"):
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("Qwen feedback JSON object not found")
        text = text[start : end + 1]
    value = json.loads(text)
    summary = _short_text(value.get("summary"), 500)
    body = _short_text(value.get("content"), 2000)
    items = value.get("priority_items", [])
    if not isinstance(items, list):
        raise ValueError("priority_items is not a list")
    priority_items = [_short_text(item, 50) for item in items[:3]]

    error_feedback = []
    for item in value.get("error_feedback", []):
        if not isinstance(item, dict) or item.get("sequence") not in error_sequences:
            continue
        error_feedback.append(
            {
                "sequence": item["sequence"],
                "summary": _short_text(item.get("summary"), 500),
                "content": _short_text(item.get("content"), 1000),
                "practice_tip": _short_text(item.get("practice_tip"), 500),
            }
        )
    return {
        "summary": summary,
        "content": body,
        "priority_items": priority_items,
        "structured_output": {"error_feedback": error_feedback},
    }


def _short_text(value, maximum):
    if not isinstance(value, str) or not (text := value.strip()) or len(text) > maximum:
        raise ValueError("invalid Qwen feedback text")
    return text

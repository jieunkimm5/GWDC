import os
from decimal import Decimal

import httpx
from dotenv import load_dotenv

from kiln_router.models import MODELS


load_dotenv()


# =========================================================
# Execution configuration
# =========================================================

LOCAL_MODEL = "qwen3-fixed"

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"

# A와 C가 공통으로 사용하는 실제 실행 모델 ID
PAID_MODELS = {
    "claude-haiku-4-5-20251001",
    "claude-sonnet-5",
    "claude-opus-5-5",
}

# A가 사용하는 가격표와 동일하게 유지
# (input USD / 1M tokens, output USD / 1M tokens)
MODEL_PRICING = {
    "claude-haiku-4-5-20251001": {
        "input": Decimal("1"),
        "output": Decimal("5"),
    },
    "claude-sonnet-5": {
        "input": Decimal("2"),
        "output": Decimal("10"),
    },
    "claude-opus-5-5": {
        "input": Decimal("4"),
        "output": Decimal("20"),
    },
}

# 실제 실행 제한: A가 비용을 계산할 때 쓴 값과 같아야 한다.
# qwen3-fixed는 qwen3:8b에 파라미터만 고정한 Ollama 모델(Modelfile)이므로
# 한도는 A에 등록된 qwen3:8b 설정을 따른다.
A_LOCAL_MODEL_ID = "qwen3:8b"
LOCAL_MAX_OUTPUT_TOKENS = MODELS[A_LOCAL_MODEL_ID].execution_max_output_tokens
LOCAL_CONTEXT_TOKENS = MODELS[A_LOCAL_MODEL_ID].execution_context_tokens

# qwen3:8b는 노트북에서 초당 약 17토큰이라 2,048토큰에 약 2분이 걸린다.
LOCAL_TIMEOUT_SECONDS = 300.0
PAID_TIMEOUT_SECONDS = 300.0


# =========================================================
# Cost calculation
# =========================================================

def calculate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> str:
    """
    실제 API 사용 token 수를 기준으로 비용 계산.
    금액 계산에는 float 대신 Decimal을 사용한다.
    """

    if model not in MODEL_PRICING:
        raise ValueError(
            f"Pricing is not configured for model: {model}"
        )

    pricing = MODEL_PRICING[model]

    input_cost = (
        Decimal(input_tokens)
        * pricing["input"]
        / Decimal("1000000")
    )

    output_cost = (
        Decimal(output_tokens)
        * pricing["output"]
        / Decimal("1000000")
    )

    total_cost = input_cost + output_cost

    return f"{total_cost:.6f}"


# =========================================================
# LOCAL execution
# =========================================================

def run_local(task: str, max_output_tokens: int) -> dict:
    # PAID 추천 후 대체 실행이면 유료 모델용 한도(예: 4096)가 들어올 수 있다.
    # 로컬 모델의 실행 한도를 넘기지 않는다.
    max_output_tokens = min(max_output_tokens, LOCAL_MAX_OUTPUT_TOKENS)

    payload = {
        "model": LOCAL_MODEL,
        "messages": [
            {
                "role": "user",
                "content": task,
            }
        ],
        "stream": False,
        "think": False,
        "options": {
            "num_predict": max_output_tokens,
            "num_ctx": LOCAL_CONTEXT_TOKENS,
        },
    }


    try:
        response = httpx.post(
            OLLAMA_URL,
            json=payload,
            timeout=LOCAL_TIMEOUT_SECONDS,
        )

        response.raise_for_status()

    except httpx.ConnectError as e:
        raise RuntimeError(
            "Ollama에 연결할 수 없습니다. "
            "Ollama가 실행 중인지 확인해주세요."
        ) from e

    except httpx.HTTPStatusError as e:
        raise RuntimeError(
            f"Ollama API error: {e.response.text}"
        ) from e

    except httpx.RequestError as e:
        raise RuntimeError(
            f"Ollama request failed: {e}"
        ) from e

    data = response.json()

    result_text = data["message"]["content"]

    # Ollama가 제공하는 실제 token usage
    input_tokens = data.get(
        "prompt_eval_count",
        0,
    )

    output_tokens = data.get(
        "eval_count",
        0,
    )

    return {
        "result": result_text,
        "actual_cost_usd": "0.000000",
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


# =========================================================
# PAID execution
# =========================================================

def run_paid(task: str, model: str, max_output_tokens: int) -> dict:


    # A가 임의의 모델을 반환하더라도 허용된 모델만 실행
    if model not in PAID_MODELS:
        raise ValueError(
            f"Unauthorized paid model: {model}"
        )

    api_key = os.getenv("PAID_LLM_API_KEY")

    if not api_key:
        raise RuntimeError(
            "PAID_LLM_API_KEY is not configured."
        )

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    payload = {
        "model": model,
        "max_tokens": max_output_tokens,
        "messages": [
            {
                "role": "user",
                "content": task,
            }
        ],
    }

    try:
        response = httpx.post(
            ANTHROPIC_URL,
            headers=headers,
            json=payload,
            timeout=PAID_TIMEOUT_SECONDS,
        )

        response.raise_for_status()

    except httpx.HTTPStatusError as e:
        raise RuntimeError(
            f"Claude API error: {e.response.text}"
        ) from e

    except httpx.RequestError as e:
        raise RuntimeError(
            f"Claude API connection failed: {e}"
        ) from e

    data = response.json()

    # Claude 응답의 text block만 합침
    text_parts = []

    for block in data.get("content", []):
        if block.get("type") == "text":
            text_parts.append(block.get("text", ""))

    result_text = "\n".join(text_parts)

    usage = data.get("usage", {})

    input_tokens = usage.get(
        "input_tokens",
        0,
    )

    output_tokens = usage.get(
        "output_tokens",
        0,
    )

    # A와 동일한 가격표를 사용해 실제 사용 비용 계산
    actual_cost = calculate_cost(
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )

    return {
        "result": result_text,
        "actual_cost_usd": actual_cost,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }

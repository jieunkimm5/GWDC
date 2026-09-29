# GWDC

사용자 작업을 Kiln으로 분석하고, 적합한 실행 모델과 예상 비용을 추천하는 AI inference purchasing agent 프로젝트입니다.

## A 모듈 개발 환경

Python 3.11을 사용합니다. A의 범위는 작업 분석·모델 추천·예상 비용 계산이며, 실행과 fallback은 C가 연결합니다.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
cp .env.example .env
python -m kiln_router
```

`.env`의 `KILN_API_KEY`에 발급받은 키를 입력합니다. `.env`는 Git에서 제외됩니다.
IDE의 Python 인터프리터는 `.venv/bin/python`을 선택합니다.

현재는 라우터와 실행 로그 연결(6단계)까지 구현되어 있습니다. `python -m kiln_router`는 설치 확인용이며 API를 호출하지 않습니다. 실행 한도는 A가 정하며, C는 아래 [C의 모델 호출 규칙](#c의-모델-호출-규칙)을 따릅니다.

### 의존성

- `httpx`: 비동기 Kiln API 통신
- `pydantic`: 입력·응답 데이터 검증
- `python-dotenv`: 로컬 `.env` 설정 로드

### 모듈 구조

```text
kiln_router/
├── schemas.py       # 입력·출력 자료형
├── models.py        # 후보 모델·단가·한도 설정
├── client.py        # Kiln API 통신
├── prompts.py       # 작업 분석 지침
├── validation.py    # 응답·입력 한도 검사
├── pricing.py       # 토큰 추정과 비용 계산
├── router.py        # 추천 흐름 연결
└── telemetry.py     # 사용량·시간·판단·오류 기록
```

## 데이터 계약 (2단계)

- `RoutingRequest`: C가 전달하는 `task` 문자열만 받습니다. 빈 작업과 추가 필드는 거부하며 코드의 들여쓰기는 보존합니다.
- `KilnEvaluationResponse`: 예상 답변 길이 `expected_output_length`(`short`/`medium`/`long`)와 `evaluations` 배열을 받습니다. 배열에는 등록된 후보 4개가 각각 한 번씩 있어야 합니다. 각 항목은 `model_id`, 불리언 `suitable`, 비어 있지 않은 `reason`입니다. 전부 부적합한 응답도 유효하며, 그 상황의 처리는 라우터 단계에서 구현합니다.
- `RoutingDecision`: C에 반환할 다섯 필드를 검증합니다. 경로와 모델이 일치해야 하며 금액은 0 이상, 소수점 6자리 문자열입니다. LOCAL 금액은 `"0.000000"`입니다. `max_output_tokens`는 양의 정수입니다.

| 필드 | 의미 |
| --- | --- |
| `recommended_route` | `"LOCAL"`(qwen3:8b) 또는 `"PAID"`(Claude 3종) |
| `selected_model` | C가 호출할 모델 ID. 경로와 일치 |
| `reason` | Kiln의 판단 이유 + A의 선택 이유 |
| `estimated_cost_usd` | `max_output_tokens`만큼 출력한다고 가정한 예상 유료 비용. B의 예산 판단 기준 |
| `max_output_tokens` | C가 호출 시 출력 상한으로 넣을 값. 견적에 쓴 출력 토큰과 같음 |

```python
from kiln_router.schemas import RoutingRequest, RoutingDecision

request = RoutingRequest.model_validate({"task": "Explain this function: ..."})

# 자료형 사용 예시이며 실제 Kiln 판단 결과는 아닙니다.
decision = RoutingDecision(
    recommended_route="LOCAL",
    selected_model="qwen3:8b",
    reason="짧은 함수 설명으로 로컬 모델이 적합합니다.",
    estimated_cost_usd="0.000000",
    max_output_tokens=512,
)
payload = decision.model_dump()  # C에 전달할 dict
```

현재 스키마 오류는 Pydantic의 `ValidationError`입니다. 이후 라우터에서 합의된 `RoutingError`로 변환합니다. `run_id`, 예산 승인 및 실제 실행 경로는 A의 입력·출력에 추가하지 않습니다.

### 모델 설정

`models.py`에 LOCAL 1개와 PAID 3개를 등록했습니다. Kiln 분석 모델은 별도 상수이며 실행 후보가 아닙니다.

| 모델 ID | 입력 / 출력 단가 (USD, 100만 토큰당) | 공개 컨텍스트 / 최대 출력 | 실행 컨텍스트 / 최대 출력 |
| --- | --- | --- | --- |
| `qwen3:8b` | 0 / 0 (유료 추론 API 비용) | 배포 설정 확인 필요 | 16,384 / 2,048 |
| `claude-haiku-4-5-20251001` | 1 / 5 | 200,000 / 64,000 | 200,000 / 4,096 |
| `claude-sonnet-5` | 2 / 10 | 1,000,000 / 128,000 | 1,000,000 / 4,096 |
| `claude-opus-5-5` | 4 / 20 | 1,000,000 / 128,000 | 1,000,000 / 4,096 |

2026-09-28 확인: [Anthropic 공식 모델 비교](https://platform.claude.com/docs/en/models/overview), [Ollama 모델](https://ollama.com/library/qwen3:8b).
단가는 일반 입력·출력 기준이며 캐시·배치 할인 등은 포함하지 않습니다. 금액 설정은 `Decimal`입니다. Kiln 분석 비용과 블록체인 수수료는 추천 비용 범위에서 제외합니다.

**공개 최대 한도와 실제 실행 한도는 다릅니다.** 실행 한도(`execution_context_tokens`, `execution_max_output_tokens`)는 A가 정한 모델별 상한입니다. 예상 답변 길이의 토큰이 출력 상한을 넘는 모델은 후보에서 제외됩니다. 값을 `None`으로 바꾸면 무제한이 아니라 미설정으로 보고 `MODEL_CONFIG_ERROR`를 냅니다.

### C의 모델 호출 규칙

A의 견적은 C가 아래 규칙대로 호출한다는 전제로 계산됩니다.

- **지침 없이 task만 전송:** 시스템 프롬프트를 붙이지 않고 사용자 task를 user 메시지 하나로 보냅니다.
- **최대 출력:** 결과의 `max_output_tokens`를 Anthropic 호출의 `max_tokens`에 넣습니다. 확장 사고를 켜면 사고 토큰도 이 한도 안에 포함됩니다.
- **로컬 Ollama:** 결과의 `max_output_tokens`를 `num_predict`에, 컨텍스트는 `num_ctx=16384`로 지정합니다. Ollama 기본 컨텍스트는 이보다 작을 수 있으므로 반드시 명시합니다.
- 답변이 한도에서 잘릴 수 있습니다(`stop_reason: "max_tokens"`). Kiln이 답변 길이를 짧게 판정했다면 잘릴 가능성이 커집니다.

### 계약 검증

```bash
python -m unittest discover -s tests -v
```

API 호출 없이 필드·자료형, 금액 형식, 경로와 모델 일치, 후보 누락·중복을 검증합니다.

## Kiln 클라이언트 (3단계)

웹 로그인 비밀번호와 API 키는 다릅니다. Kiln 콘솔에서 API 키를 발급해 `.env`의 `KILN_API_KEY`에 입력합니다. 키·비밀번호를 소스나 README에 기록하지 않습니다.

```bash
# 실제 Kiln 호출 1회: 팀 크레딧이 사용됩니다.
python -m kiln_router.smoke
```

성공하면 호출 모델, 토큰 수, 소요 시간, completion ID, generation ID, 제공되는 경우 Kiln 과금액을 `logs/kiln_smoke.jsonl`에 기록합니다. 이 파일은 Git에서 제외되며, 키·프롬프트·응답 전문은 저장하지 않습니다. 연결 확인은 `kiln_smoke` 흐름으로 표시하며 실제 라우팅 데모 증빙을 대신하지 않습니다.

```python
from kiln_router.client import KilnClient, KilnSettings

async def example():
    async with KilnClient(KilnSettings.from_env()) as client:
        response = await client.complete(
            system_prompt="Answer briefly.",
            task="Reply with the word OK.",
        )
    return response.content, response.log_metadata()
```

- 운영진의 모델 변경 공지에 따라 `httpx`로 `qwen3-32b`의 `/chat/completions`를 비동기 호출합니다. LOCAL 실행 모델 `qwen3:8b`와는 별개입니다.
- 기본 설정은 비스트리밍, 전체 제한 시간 60초, `max_tokens=2048`입니다. 이전 모델용 `reasoning_effort`는 보내지 않습니다. 이는 Kiln 분석용 설정이며 C의 실행 모델 한도와 다릅니다.
- 과금 요청의 중복 실행을 피하려고 자동 재시도는 하지 않습니다. 시간 초과 시 서버에서 처리됐는지는 불명확할 수 있습니다.
- `RoutingError.code`로 설정·인증·크레딧·호출 제한·시간 초과·네트워크·응답 오류를 구분합니다. 원시 오류 본문은 노출하지 않습니다.
- 잘린 응답과 빈 응답은 정상 추천으로 반환하지 않으며, 파싱 가능한 사용량은 오류 메타데이터에 보존합니다. 사용량이 없거나 잘못된 응답은 0토큰으로 처리하지 않습니다.
- 클라이언트는 응답 텍스트를 반환합니다. 라우터가 `parse_evaluations`로 후보 평가를 검증하고 비용 계산까지 연결합니다.

공식 문서: [Kiln API](https://kiln.bricksum.com/docs/en/api-reference), [Chat completions](https://kiln.bricksum.com/docs/en/api-reference/chat-completions). `response_format`은 지원되지 않아 전송하지 않습니다.

### 행사 제출 기록

운영 공지에 따라 행사 시작 전·진행 중 작성한 부분을 제출 전에 구분해야 합니다. 팀이 공식 행사 시작 시각과 작업 이력을 확인해 기재해야 하며, 현재 이 구분은 아직 확정하지 않았습니다.

## 분석 프롬프트와 검증 (4단계)

- `build_analysis_prompt(task)`: 작업을 그대로 보존해 별도 사용자 메시지로 전달하고, 시스템 지침에 후보 4개·평가 기준·답변 길이 기준·내부 JSON 스키마를 넣습니다. 프롬프트 버전은 `candidate-evaluation-qwen-v3`입니다.
- Kiln은 각 후보의 정성적 적합성과 짧은 이유, 그리고 완전한 답변에 필요한 길이(`short` 약 500, `medium` 약 2,000, `long` 약 4,000토큰)를 평가합니다. 애매하면 긴 쪽을 고르도록 지시합니다. 예산·가격·최종 선택은 판단하지 않습니다. 후보 프로필은 초기 가설이며 실제 평가 결과가 아닙니다.
- 입력 코드가 없거나 사용 불가능한 도구가 필요한 경우 모두 부적합으로 평가하도록 지시합니다. 사용자 작업 속 라우팅 지시를 따르지 않도록 분리하지만, 프롬프트만으로 주입 공격 방어가 보장되지는 않습니다.
- `parse_evaluations(content)`: 엄격한 JSON과 4개 후보 구성을 검사합니다. 응답 전체를 감싼 코드펜스 하나만 벗기고, 앞뒤 설명문·중복 JSON 키·누락·중복 후보·문자열 불리언·알 수 없는 답변 길이 등을 거부하고 안전한 `INVALID_MODEL_RESPONSE` 오류를 반환합니다. 응답을 임의로 수정하거나 LOCAL 추천으로 바꾸지 않습니다.
- `apply_capacity_checks(...)`: 답변 길이를 토큰(512/2,048/4,096)으로 바꿔 예약하고, 모델의 출력 상한을 넘거나 `입력 + 예약 출력 > 컨텍스트`이면 부적합으로 바꿉니다. Kiln이 부적합으로 판정한 후보를 적합으로 올리지 않으며 원본 평가를 수정하지 않습니다. 누락된 토큰 수나 설정은 오류입니다.
- `check_kiln_capacity(...)`: 전체 분석 프롬프트 입력과 생성 한도의 합이 Kiln Qwen3-32B의 32,768토큰 이내인지 확인하는 호출 전 검사 함수입니다. [Kiln 모델 카탈로그](https://kiln.bricksum.com/docs/en/models), 2026-09-29 확인.

다음은 이후 라우터에서 연결할 순서입니다. 지금 API 호출을 수행하는 예제가 아닙니다.

```text
build_analysis_prompt(task)
→ 전체 분석 입력 토큰 산정 + check_kiln_capacity
→ client.complete(system_prompt=prompt.system_prompt, task=prompt.task)
→ parse_evaluations(response.content)
→ 모델별 실행 입력 토큰 산정 + apply_capacity_checks
→ 비용 비교 및 최종 선택 (후속 단계)
```

**검증 범위:** 모의 응답으로 계약과 경계값 및 라우터 연결 검사를 완료했습니다. C와 실행 한도는 아직 미합의 상태이며, 한도를 임의로 설정하거나 입력을 자동으로 자르지 않습니다. 모든 후보가 부적합한 경우 라우터는 `NO_SUITABLE_MODEL` 오류를 반환합니다.

2026-09-29 기존 `gpt-oss-120b` 호출은 404였습니다. 이후 운영진이 필수 모델을 Qwen3-32B로 변경한다고 공지하여 `qwen3-32b`로 전환했습니다. 자동 대체가 아닌 공식 요구사항 변경을 반영한 것입니다.

## 비용 계산기 (5단계)

`pricing.py`는 사용자 예산을 받거나 승인하지 않습니다. Kiln 분석·블록체인·장비 비용을 제외한 실행 모델의 유료 추론 비용만 계산합니다. API 호출은 없습니다.

| 함수/자료형 | 역할 |
| --- | --- |
| `ExecutionInput` | C가 보낼 실행용 시스템 지침과 사용자 작업을 보존 |
| `estimate_input_tokens` | 전체 텍스트 요청의 입력 토큰 근사 추정 |
| `InputTokenEstimate` | 입력 토큰 수와 계산 방법 기록 |
| `estimate_model_cost` | 후보 하나의 입력·출력 비용과 합계 계산 |
| `estimate_candidate_costs` | 후보별 입력 수용 검사 후 적합한 후보의 비용을 오름차순 반환 |
| `CostEstimate.log_metadata()` | 추정 방법·토큰·단가·계산 근거 반환 (원문 제외) |

계산식은 `(입력 토큰 × 입력 단가 + 예약 출력 토큰 × 출력 단가) / 1,000,000`입니다. 단가와 계산은 Decimal로 처리하며 합계를 소수점 6자리에서 올림합니다. 후보 비교는 올림 전 금액을 사용합니다. 동일 금액이면 LOCAL → Haiku → Sonnet → Opus 순서로 정합니다. LOCAL의 유료 API 비용은 0입니다.

### 현재 추정 정책과 한계

- **입력:** `utf8-envelope-v1`은 텍스트의 UTF-8 바이트 수 + 요청 기본 여유 32 + 메시지당 여유 16으로 계산하는 임시 근사치입니다. 이는 모델 토크나이저 결과나 입증된 상한이 아닙니다. 입력을 크게 추정하여 실제 처리 가능한 후보를 제외하거나 비용을 과대평가할 수 있습니다. 같은 요청이면 기본 추정값은 모델 간 동일합니다.
- `token_counter`를 주입하면 모델별 토크나이저나 제공업체의 전체 요청 카운트 결과로 대체할 수 있습니다. `InputTokenEstimate.method`에 출처를 기록합니다. 아직 실측 보정은 하지 않았습니다.
- **출력:** Kiln의 답변 길이 판정(`short` 512 / `medium` 2,048 / `long` 4,096토큰)을 예약합니다. 같은 값을 `max_output_tokens`로 C에 넘기므로 출력 비용은 견적을 넘지 않습니다. 이 값은 과금 추론 토큰까지 포함합니다. 입력 근사 오차 때문에 실제 요금의 확정 상한은 아닙니다. `estimate_model_cost`에 출력 토큰을 주지 않으면 모델 출력 상한 전체를 예약합니다.
- 텍스트 시스템 메시지와 사용자 작업만 대상으로 합니다. 도구·이미지·대화 이력이 추가되면 요청 구조와 계산기를 확장해야 합니다. 캐시·배치 할인은 적용하지 않습니다.
- 실행 한도가 `None`이면 `MODEL_CONFIG_ERROR`입니다. 실제 호출에 한도를 적용하는 것은 C, 최종 예산 보호는 B가 처리합니다.
- 적합한 후보가 없으면 계산기는 빈 견적 목록을 반환하고 라우터가 `NO_SUITABLE_MODEL` 오류를 전달합니다. 자동 LOCAL 추천이나 0원짜리 유료 견적을 만들지 않습니다.

계산 예시(토큰과 한도는 설명용 가정):

```python
from dataclasses import replace
from kiln_router.models import MODELS
from kiln_router.pricing import InputTokenEstimate, estimate_model_cost

# 팀의 실행 설정을 변경하지 않는 예시입니다.
model = replace(MODELS["claude-sonnet-5"],
                execution_context_tokens=8192,
                execution_max_output_tokens=1000)
quote = estimate_model_cost(model, InputTokenEstimate(2000, "example_assumption"))
print(quote.estimated_cost_usd)  # 0.014000
```

비용 계산·올림·동률·모델별 입력 추정·한도 초과 제외·부적합 후보 제외를 오프라인 테스트로 검증합니다. 실제 모델 사용량과의 비교는 추후 수행해야 합니다.

## 라우터와 로그 (6단계)

`KilnRouter`는 C가 초기화하고 `await router.recommend_route(task)`로 호출합니다. 요청별 입력은 여전히 task 하나이며 예산과 run_id를 받지 않습니다. 기본값은 `models.py`의 실행 한도와 지침 없는 실행이며, C는 [호출 규칙](#c의-모델-호출-규칙)을 따릅니다.

```python
from kiln_router.client import KilnClient, KilnSettings
from kiln_router.router import KilnRouter

async def recommend(task):
    async with KilnClient(KilnSettings.from_env()) as client:
        router = KilnRouter(client)
        decision = await router.recommend_route(task)
        return decision.model_dump()  # 합의한 다섯 필드
```

처리 순서:

1. 입력·설정과 분석 요청의 추정 토큰 한도를 검사합니다. 실패하면 API를 호출하지 않습니다.
2. Kiln을 한 번 호출하고 사용량 메타데이터를 보존합니다.
3. 후보별 평가와 답변 길이 JSON을 검사하고, 코드로 출력·컨텍스트 한도를 적용합니다.
4. 적합한 후보를 예상 비용으로 비교합니다. 적합한 LOCAL은 0원이라 우선 선택됩니다.
5. 다섯 필드의 `RoutingDecision`을 반환하거나 `RoutingError`를 전달합니다. 승인·결제·모델 실행·fallback은 수행하지 않습니다.

`logs/routing.jsonl`에 호출당 JSON 한 줄을 기록합니다. 파일은 Git에서 제외됩니다.

- A 내부 `analysis_id`(호출별 UUID), 시각, 단계, 상태, 전체 소요 시간
- 프롬프트 버전, 분석 모델, 추정 입력량과 실행 한도
- 실제 Kiln 사용량·과금액(제공된 경우)·호출 식별자, 재시도 횟수 0
- 예상 답변 길이, 원래 후보 평가와 한도 검사 후 평가, 후보별 비용 근거, 최종 결정
- 오류 코드와 HTTP 상태 (알 수 없는 사용량은 0이 아닌 null)

`analysis_id`는 C의 `run_id`를 대신하지 않습니다. 최종 다섯 필드에 추가하지 않으며, C의 실행 이력과 A 내부 로그 연결은 별도 통합 작업입니다. 원본 task·프롬프트·API 응답 전문·API 키는 로그에 넣지 않습니다. 다만 모델이 작성한 짧은 판단 이유는 작업 내용을 인용할 수 있어 제출용 로그는 검토해야 합니다. 설정된 키 문자열은 로그에서 추가로 제거합니다.

응답 JSON 검증이나 후보 선택 실패 후에도 받은 Kiln 사용량을 보존합니다. 시간 초과 등 사용량을 받지 못한 경우에는 null이며 과금되지 않았다는 뜻이 아닙니다. 로그 저장 실패 시 정상 결과 대신 `TELEMETRY_ERROR`를 알립니다. 이미 다른 오류가 발생했다면 기존 오류를 유지하고 로그 저장 실패 경고를 냅니다.

모의 HTTP 응답을 사용한 통합 테스트를 완료했습니다. 실제 필수 모델 호출, 판단 품질 검증, C의 실행 설정 합의는 아직 남아 있습니다.

## 사용자 입력으로 추천 확인

```bash
source .venv/bin/activate
python -m kiln_router.classify
```

입력한 작업을 C와 같은 `KilnRouter`로 실제 분석해 예상 답변 길이, 후보 4개의 적합/부적합·이유·예상 비용, C에 전달될 최종 다섯 필드를 출력합니다. 한도 검사로 빠진 후보는 `부적합 (실행 한도 초과)`로 표시합니다. 여러 줄의 코드와 지시문은 UTF-8 파일에 넣고 다음처럼 전달할 수 있습니다.

```bash
python -m kiln_router.classify --file task.txt
```

실제 모델 실행·결제는 하지 않습니다. Kiln 크레딧은 사용되며, 라우터 로그와 같은 형식의 기록을 `flow: "classification_check"`로 `logs/classification.jsonl`에 저장해 C의 실제 라우팅 기록(`logs/routing.jsonl`)과 섞이지 않게 합니다. 모델 접근 오류가 나면 모의 추천으로 대체하지 않고 실패를 표시합니다.

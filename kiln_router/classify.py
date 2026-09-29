"""Interactive, real Kiln routing check; no model execution or budget approval.

Runs the same KilnRouter C uses, then prints per-candidate suitability and cost
plus the exact decision C would receive.
"""

import argparse
import asyncio
import json
from pathlib import Path

from .client import KilnClient, KilnSettings
from .errors import RoutingError
from .models import KILN_MODEL_ID, MODELS, OUTPUT_LENGTH_TOKENS
from .router import KilnRouter
from .schemas import RoutingDecision
from .telemetry import JsonlTelemetry


class CapturingTelemetry:
    """Keep the router's (already redacted) event for display, logged as a check."""

    def __init__(self, path: str | Path = "logs/classification.jsonl"):
        self._log = JsonlTelemetry(path)
        self.event: dict | None = None

    def write(self, event: dict) -> None:
        # Mark as a manual check so it is never mistaken for C's routing evidence.
        self.event = {**event, "flow": "classification_check"}
        self._log.write(self.event)


async def classify_task(task: str, client: KilnClient,
                        telemetry: CapturingTelemetry) -> RoutingDecision:
    return await KilnRouter(client, telemetry=telemetry).recommend_route(task)


def format_report(event: dict) -> str:
    lines = []
    length = event.get("expected_output_length")
    if length:
        lines.append(f"예상 답변 길이: {length} ({OUTPUT_LENGTH_TOKENS[length]} 토큰 예약)")
    raw = {item["model_id"]: item for item in
           (event.get("raw_assessment") or {}).get("evaluations", [])}
    checked = (event.get("checked_assessment") or event.get("raw_assessment") or {}).get("evaluations", [])
    costs = {item["model_id"]: item["estimated_cost_usd"] for item in event.get("cost_estimates", [])}
    if checked:
        lines.append("후보별 적합성과 예상 비용:")
    for item in checked:
        model_id = item["model_id"]
        if item["suitable"]:
            label = f"적합 · ${costs[model_id]}" if model_id in costs else "적합"
        elif raw.get(model_id, {}).get("suitable"):
            label = "부적합 (실행 한도 초과)"
        else:
            label = "부적합"
        lines.append(f"- [{MODELS[model_id].route}] {model_id}: {label}")
        lines.append(f"  {item['reason']}")
    if event.get("decision"):
        lines.append("\n최종 추천 (C에 전달되는 값):")
        lines.append(json.dumps(event["decision"], ensure_ascii=False, indent=2))
    usage = event.get("kiln_usage")
    if usage:
        cost = f", 과금 ${usage['kiln_cost_usd']}" if usage.get("kiln_cost_usd") else ""
        lines.append(f"\nKiln 토큰: 입력 {usage['input_tokens']}, 출력 {usage['output_tokens']}{cost}")
    return "\n".join(lines)


async def run(task: str, log_path: str | Path = "logs/classification.jsonl") -> int:
    telemetry = CapturingTelemetry(log_path)
    try:
        async with KilnClient(KilnSettings.from_env()) as client:
            await classify_task(task, client, telemetry)
        error = None
    except RoutingError as exc:
        error = exc
    if telemetry.event:
        print("\n" + format_report(telemetry.event))
    if error is None:
        print("\n비용은 유료 추론의 예상 최대치이며, 모델 실행·결제는 하지 않았습니다.")
        return 0
    print(f"\n추천 실패: {error.code}" + (f" (HTTP {error.status_code})" if error.status_code else ""))
    if error.status_code == 404:
        print(f"필수 모델 {KILN_MODEL_ID} 호출을 사용할 수 없습니다. 운영진에게 모델 접근을 확인해 주세요.")
    if error.code == "NO_SUITABLE_MODEL":
        print("적합한 후보가 없습니다. 작업에 필요한 자료가 빠졌거나 실행 한도를 넘는지 확인해 주세요.")
    print("최종 추천은 생성되지 않았습니다.")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Kiln으로 작업의 후보별 적합성·예상 비용·최종 추천을 확인합니다 (API 크레딧 사용).")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--task", help="분석할 작업")
    group.add_argument("--file", type=Path, help="작업과 코드를 담은 UTF-8 파일")
    args = parser.parse_args()
    try:
        task = (args.file.read_text(encoding="utf-8") if args.file is not None
                else args.task if args.task is not None else input("분석할 작업을 입력하세요: "))
    except (OSError, UnicodeError, EOFError):
        print("입력을 읽지 못했습니다. --task 또는 UTF-8 --file을 사용해 주세요.")
        return 1
    print("실제 Kiln API로 작업을 분석합니다. 모델 실행·결제는 하지 않습니다.")
    return asyncio.run(run(task))


if __name__ == "__main__":
    raise SystemExit(main())

"""Registered candidates, prices, and the execution limits C must call with."""

from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from typing import Literal, Mapping

Route = Literal["LOCAL", "PAID"]
OutputLength = Literal["short", "medium", "long"]
ModelId = Literal[
    "qwen3:8b",
    "claude-haiku-4-5-20251001",
    "claude-sonnet-5",
    "claude-opus-5-5",
]

KILN_MODEL_ID = "qwen3-32b"
# Kiln catalog verified 2026-09-29; prompt and completion combined.
KILN_CONTEXT_TOKENS = 32_768
# Kiln's expected answer length -> output tokens reserved, priced and sent to C
# as max_output_tokens. A tier above a model's execution cap excludes that model.
OUTPUT_LENGTH_TOKENS: Mapping[str, int] = MappingProxyType({
    "short": 512, "medium": 2_048, "long": 4_096,
})
ANTHROPIC_SOURCE = "https://platform.claude.com/docs/en/models/overview"
OLLAMA_SOURCE = "https://ollama.com/library/qwen3:8b"


@dataclass(frozen=True)
class ModelConfig:
    model_id: ModelId
    route: Route
    provider: Literal["ollama", "anthropic"]
    input_usd_per_million: Decimal
    output_usd_per_million: Decimal
    published_context_tokens: int | None
    published_max_output_tokens: int | None
    source_url: str
    verified_on: str = "2026-09-28"
    # A defines these; C sends the task alone, with no system prompt, and the
    # decision's max_output_tokens. None means not configured, not unlimited.
    execution_context_tokens: int | None = None
    execution_max_output_tokens: int | None = None


MODELS: Mapping[str, ModelConfig] = MappingProxyType({
    "qwen3:8b": ModelConfig(
        model_id="qwen3:8b",
        route="LOCAL",
        provider="ollama",
        input_usd_per_million=Decimal("0"),
        output_usd_per_million=Decimal("0"),
        published_context_tokens=None,
        published_max_output_tokens=None,
        source_url=OLLAMA_SOURCE,
        execution_context_tokens=16_384,
        execution_max_output_tokens=2_048,
    ),
    "claude-haiku-4-5-20251001": ModelConfig(
        model_id="claude-haiku-4-5-20251001",
        route="PAID",
        provider="anthropic",
        input_usd_per_million=Decimal("1"),
        output_usd_per_million=Decimal("5"),
        published_context_tokens=200_000,
        published_max_output_tokens=64_000,
        source_url=ANTHROPIC_SOURCE,
        execution_context_tokens=200_000,
        execution_max_output_tokens=4_096,
    ),
    "claude-sonnet-5": ModelConfig(
        model_id="claude-sonnet-5",
        route="PAID",
        provider="anthropic",
        input_usd_per_million=Decimal("2"),
        output_usd_per_million=Decimal("10"),
        published_context_tokens=1_000_000,
        published_max_output_tokens=128_000,
        source_url=ANTHROPIC_SOURCE,
        execution_context_tokens=1_000_000,
        execution_max_output_tokens=4_096,
    ),
    "claude-opus-5-5": ModelConfig(
        model_id="claude-opus-5-5",
        route="PAID",
        provider="anthropic",
        input_usd_per_million=Decimal("4"),
        output_usd_per_million=Decimal("20"),
        published_context_tokens=1_000_000,
        published_max_output_tokens=128_000,
        source_url=ANTHROPIC_SOURCE,
        execution_context_tokens=1_000_000,
        execution_max_output_tokens=4_096,
    ),
})

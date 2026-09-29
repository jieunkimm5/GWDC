import asyncio
import os

from dotenv import load_dotenv

from app.schemas import RouterResult
from kiln_router.client import KilnClient, KilnSettings
from kiln_router.router import KilnRouter


load_dotenv()


async def _analyze_async(task: str) -> RouterResult:
    """
    실제 Kiln API를 사용해서 A의 routing decision을 가져온다.
    """

    api_key = os.getenv("KILN_API_KEY")

    if not api_key:
        raise RuntimeError(
            "KILN_API_KEY is not configured."
        )

    api_url = (
        os.getenv("KILN_API_URL")
        or "https://api.bricksum.com/v1"
    )

    settings = KilnSettings(
        api_key=api_key,
        api_url=api_url,
    )

    async with KilnClient(settings) as client:
        router = KilnRouter(client)

        decision = await router.recommend_route(task)

    # A의 RoutingDecision
    # ↓
    # C에서 사용하는 RouterResult
    return RouterResult(
        recommended_route=decision.recommended_route,
        selected_model=decision.selected_model,
        reason=decision.reason,
        estimated_cost_usd=decision.estimated_cost_usd,
        max_output_tokens=decision.max_output_tokens,
    )


def analyze(task: str) -> RouterResult:
    """
    C workflow에서 기존 analyze(task) 형태를
    그대로 사용할 수 있도록 sync adapter 제공.
    """

    return asyncio.run(
        _analyze_async(task)
    )
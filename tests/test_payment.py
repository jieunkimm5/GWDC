from app.blockchain.mock_payment import authorize


print("=== Demo 1: Budget $0.05 ===")

result1 = authorize(
    run_id="run_001",
    decision="PAID",
    provider="paid-model-1",
    budget_usd="0.050000",
    estimated_cost_usd="0.032000"
)

print(result1)


print("\n=== Demo 2: Budget $0 ===")

result2 = authorize(
    run_id="run_002",
    decision="PAID",
    provider="paid-model-1",
    budget_usd="0.000000",
    estimated_cost_usd="0.032000"
)

print(result2)
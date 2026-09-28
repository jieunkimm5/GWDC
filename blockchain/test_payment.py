from payment import authorize


print("=== TEST 1: budget sufficient ===")

result1 = authorize(
    run_id="run_001",
    decision="PAID",
    provider="paid-model-1",
    budget_usd="0.050000",
    estimated_cost_usd="0.032000",
)

print(result1)


print("\n=== TEST 2: budget insufficient ===")

result2 = authorize(
    run_id="run_002",
    decision="PAID",
    provider="paid-model-1",
    budget_usd="0.000000",
    estimated_cost_usd="0.032000",
)

print(result2)
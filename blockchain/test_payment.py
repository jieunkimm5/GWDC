from blockchain.payment import authorize


print("================================")
print("TEST 1 - Budget sufficient")
print("================================")

result1 = authorize(
    run_id="run_001",
    decision="PAID",
    provider="paid-model-1",
    budget_usd="0.050000",
    estimated_cost_usd="0.032000",
)

print(result1)


print("\n================================")
print("TEST 2 - Budget insufficient")
print("================================")

result2 = authorize(
    run_id="run_002",
    decision="PAID",
    provider="paid-model-1",
    budget_usd="0.000000",
    estimated_cost_usd="0.032000",
)

print(result2)
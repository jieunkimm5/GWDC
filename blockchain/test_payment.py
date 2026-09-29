from blockchain.payment import authorize, settle_payment


print("================================")
print("TEST 1 - Budget sufficient")
print("================================")

result1 = authorize(
    run_id="run_001",
    decision="PAID",
    provider="claude-sonnet-5",
    budget_usd="20.000000",
    estimated_cost_usd="5.000000",
)

print(result1)


print("\n================================")
print("TEST 2 - Actual cost exceeds estimate")
print("================================")

settlement1 = settle_payment(
    estimated_cost_usd="5.000000",
    actual_cost_usd="10.000000",
)

print(settlement1)


print("\n================================")
print("TEST 3 - Actual cost below estimate")
print("================================")

settlement2 = settle_payment(
    estimated_cost_usd="5.000000",
    actual_cost_usd="3.000000",
)

print(settlement2)


print("\n================================")
print("TEST 4 - Budget insufficient")
print("================================")

result2 = authorize(
    run_id="run_002",
    decision="PAID",
    provider="claude-sonnet-5",
    budget_usd="2.000000",
    estimated_cost_usd="5.000000",
)

print(result2)
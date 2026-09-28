from policy import check_budget


print(
    check_budget(
        budget_usd="0.050000",
        estimated_cost_usd="0.032000",
    )
)

print(
    check_budget(
        budget_usd="0.000000",
        estimated_cost_usd="0.032000",
    )
)

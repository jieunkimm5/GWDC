from app.services.workflow import run_workflow


task = "Analyze this code and find the bug."


print("================================")
print("DEMO 1 - Budget $0.05")
print("================================")

result1 = run_workflow(
    task=task,
    budget_usd="0.050000"
)

print(result1.model_dump_json(indent=2))


print("\n================================")
print("DEMO 2 - Budget $0")
print("================================")

result2 = run_workflow(
    task=task,
    budget_usd="0.000000"
)

print(result2.model_dump_json(indent=2))
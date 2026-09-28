from app.services.executor import run_local, run_paid


print("=== LOCAL TEST ===")

local_result = run_local(
    "Analyze this code and find the bug."
)

print(local_result)


print("\n=== PAID TEST ===")

paid_result = run_paid(
    "Analyze this code and find the bug.",
    "paid-model-1"
)

print(paid_result)
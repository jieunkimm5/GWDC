# Agent Finance

> **An AI inference purchasing agent that allows users to submit an AI task with a maximum spending budget, uses Kiln to choose between local and paid LLM execution, verifies budget constraints before paid inference, and records payment authorization on the blockchain.**

---

##  What We Built

**Agent Finance** is an AI inference purchasing agent that automatically determines how an AI task should be executed based on the task requirements and the user's budget.

The user provides:

- an **AI task**
- a **maximum spending budget**

Agent Finance then uses **Kiln** to analyze the task and determine an appropriate execution model.

The system supports two execution paths:

| Route | Model | Description |
|---|---|---|
| **LOCAL** | `qwen3:8b` | Runs locally through Ollama with no paid inference cost |
| **PAID** | Claude models | Uses a paid Anthropic model when stronger inference is needed |

When Kiln recommends a paid model, Agent Finance checks whether the estimated inference cost is within the user's budget.

Only when the budget check and blockchain authorization succeed does the system execute the paid model.

If the budget is insufficient, blockchain authorization fails, or paid inference cannot proceed, Agent Finance safely falls back to the local model.

---

## How It Works

The overall Agent Finance workflow is:

```text
User
 │
 │  Task + Maximum Budget
 ▼
Kiln Router
 │
 │  Analyze the task
 │  Select an execution model
 │  Estimate inference cost
 ▼
Routing Decision
 │
 ├── LOCAL
 │     │
 │     ▼
 │   qwen3:8b
 │   via Ollama
 │
 └── PAID
       │
       ▼
   Budget Check
       │
       ├── Budget Insufficient
       │      │
       │      ▼
       │   Local Fallback
       │
       └── Budget Approved
              │
              ▼
       Blockchain Authorization
          on Sepolia
              │
              ▼
        Paid LLM Execution
              │
              ▼
       Actual Cost Settlement
              │
              ▼
          Final Response
```

### Flow

1. The user submits an **AI task** and a **maximum budget**.
2. **Kiln** analyzes the task.
3. Kiln recommends either a local or paid execution model.
4. Kiln estimates the expected inference cost.
5. If the selected route is `LOCAL`, the task is executed using `qwen3:8b`.
6. If the selected route is `PAID`, the payment layer compares the estimated cost with the user's budget.
7. If the budget is insufficient, the system falls back to the local model.
8. If the budget is sufficient, the authorization decision is recorded on the **Sepolia testnet**.
9. Only after successful blockchain authorization is the paid LLM executed.
10. The system calculates the actual inference cost using real token usage.
11. Agent Finance returns the final AI result together with routing, payment, cost, and token usage information.

---

##  Kiln API

Kiln is used as the **AI routing layer** of Agent Finance.

Kiln analyzes the user's task using:

```text
qwen3-32b
```

and determines which execution model is suitable for the task.

### Available Execution Models

| Route | Model |
|---|---|
| LOCAL | `qwen3:8b` |
| PAID | `claude-haiku-4-5-20251001` |
| PAID | `claude-sonnet-5` |
| PAID | `claude-opus-5-5` |

The Kiln router returns information in the following form:

```json
{
  "recommended_route": "PAID",
  "selected_model": "claude-sonnet-5",
  "reason": "The model is suitable for the requested reasoning task.",
  "estimated_cost_usd": "0.020880",
  "max_output_tokens": 2048
}
```

### Separation of Responsibilities

Kiln is responsible for:

- analyzing the task
- selecting an appropriate model
- estimating inference cost
- determining the maximum output token budget

Kiln does **not** directly authorize spending.

The actual spending decision is handled separately by the budget and blockchain authorization layer.

This separation prevents the AI router from directly authorizing its own paid inference.

---

##  Blockchain Integration

Agent Finance uses the **Ethereum Sepolia testnet** to create an auditable record before paid inference is executed.

When Kiln recommends a paid model and the user's budget is sufficient, Agent Finance submits an authorization transaction to the blockchain.

The recorded decision includes information such as:

```text
run_id
decision
approved
amount
provider
```

Example:

```text
run_id   : run_6fc994dd
decision : PAID
approved : true
amount   : 0.020880
provider : claude-sonnet-5
```

### Why Blockchain?

The blockchain layer provides an external and verifiable record that:

- a paid inference decision was made
- the request was approved
- the expected amount was known before execution
- the selected provider was recorded

A paid model is executed only after successful blockchain authorization.

If the blockchain transaction fails, Agent Finance does **not** intentionally call the paid API and instead falls back to local inference.

---

##  Cost Settlement

Agent Finance distinguishes between five different cost values:

| Field | Meaning |
|---|---|
| `budget_usd` | Maximum amount the user is willing to spend |
| `estimated_cost_usd` | Estimated inference cost before execution |
| `actual_cost_usd` | Actual inference cost after execution |
| `user_charge_usd` | Final amount charged to the user |
| `platform_charge_usd` | Cost covered by Agent Finance |

The estimated cost is calculated before paid inference.

The actual cost is calculated after execution using the real input and output token usage.

### Settlement Rule

The user is never charged more than the estimated cost.

```text
user_charge = min(actual_cost, estimated_cost)
```

If the actual cost exceeds the estimate:

```text
platform_charge = actual_cost - estimated_cost
```

Otherwise:

```text
platform_charge = 0
```

### Example

```text
Estimated Cost  : $0.020000
Actual Cost     : $0.030000

User Charge     : $0.020000
Platform Charge : $0.010000
```

This protects the user from unexpected cost increases after paid inference has already been authorized.

---

## On-chain Proof

The following is a successful paid inference authorization recorded on the **Sepolia testnet**.

### Testnet Transaction

```text
Network          : Ethereum Sepolia Testnet
Contract Address : 0xAec70Ac940B1E66b73d268cA8D35908BD669CC48
Run ID           : run_9f80f3ba
Block Number     : 11807573
Status           : 1 (Success)

Transaction Hash:
0xea69f223d5a7cd8e9ca0d54f7ac9bbb2db92fc9316ee5b7d30c3ea4840f2be6a
```

[View transaction on Sepolia Etherscan](https://sepolia.etherscan.io/tx/0xea69f223d5a7cd8e9ca0d54f7ac9bbb2db92fc9316ee5b7d30c3ea4840f2be6a)

### On-chain Event Log

The transaction emitted the following `DecisionRecorded` event:

```text
run_id    : run_9f80f3ba
decision  : PAID
approved  : true
amount    : 0.011272
provider  : claude-haiku-4-5-20251001
timestamp : 1790684568
```

### Matching Contract Record

Reading the same `run_id` from the deployed `DecisionRegistry` contract returned:

```text
run_id    : run_9f80f3ba
decision  : PAID
approved  : true
amount    : 0.011272
provider  : claude-haiku-4-5-20251001
timestamp : 1790684568
```

### Matching Agent Finance Execution

```text
Run ID            : run_9f80f3ba
Status            : SUCCESS
Recommended Route : PAID
Actual Route      : PAID
Selected Model    : claude-haiku-4-5-20251001

Budget            : $0.050000
Estimated Cost    : $0.011272
Actual Cost       : $0.004293
User Charge       : $0.004293
Platform Charge   : $0.000000

Payment Approved  : true
```

The transaction event log, contract record, and Agent Finance execution share the same `run_id` and authorization data.

---

##  Failure & Fallback Behavior

Agent Finance follows a fail-safe execution policy.

| Situation | Behavior |
|---|---|
| Kiln recommends `LOCAL` | Execute using `qwen3:8b` |
| Kiln recommends `PAID` and budget is sufficient | Blockchain authorization → Paid inference |
| Budget is insufficient | Local fallback |
| Blockchain authorization fails | Local fallback |
| Paid LLM API fails | Local fallback |
| Kiln cannot select a suitable model | Local fallback |

This design prevents paid inference from proceeding when payment authorization has failed.

---

##  API

Agent Finance provides a FastAPI backend.

### Health Check

```http
GET /health
```

Example response:

```json
{
  "status": "ok"
}
```

---

### Run Agent

```http
POST /api/run
```

Example request:

```json
{
  "task": "Analyze this Python code and identify the bug.",
  "budget_usd": "0.050000"
}
```

Example response structure:

```json
{
  "run_id": "run_6fc994dd",
  "status": "SUCCESS",

  "decision": {
    "recommended_route": "PAID",
    "actual_route": "PAID",
    "selected_model": "claude-sonnet-5",
    "reason": "The model is suitable for the requested task.",
    "fallback_reason": null
  },

  "cost": {
    "budget_usd": "0.050000",
    "estimated_cost_usd": "0.020880",
    "actual_cost_usd": "0.007982",
    "user_charge_usd": "0.007982",
    "platform_charge_usd": "0.000000"
  },

  "payment": {
    "approved": true,
    "tx_hash": "0xc281..."
  },

  "usage": {
    "input_tokens": 61,
    "output_tokens": 786
  },

  "result": "..."
}
```

---

### Get Previous Run

```http
GET /api/runs/{run_id}
```

This endpoint returns a previously stored run result while the backend process is running.

---

#  How to Run

## 1. Requirements

Before running Agent Finance, make sure the following are available:

- Python 3.11
- Git
- Ollama
- Kiln API credentials
- Anthropic API credentials
- Sepolia RPC endpoint
- Sepolia wallet
- Deployed smart contract address

---

## 2. Clone the Repository

```bash
git clone https://github.com/jieunkimm5/GWDC.git
cd GWDC
```

---

## 3. Create a Virtual Environment

```bash
python -m venv .venv
```

### Windows

```bash
.venv\Scripts\activate
```

### macOS / Linux

```bash
source .venv/bin/activate
```

---

## 4. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 5. Install the Local Model

Agent Finance uses `qwen3:8b` as its local inference model.

Install Ollama and run:

```bash
ollama pull qwen3:8b
```

Make sure Ollama is running before starting Agent Finance.

---

## 6. Configure Environment Variables

Create a `.env` file in the project root.

```env
# Kiln API
KILN_API_URL=https://api.bricksum.com/v1
KILN_API_KEY=

# Paid LLM API
PAID_LLM_API_KEY=

# Blockchain
RPC_URL=
BLOCKCHAIN_PRIVATE_KEY=
CONTRACT_ADDRESS=
```

>  Never commit your `.env`, private key, or API keys to GitHub.

---

## 7. Start the FastAPI Backend

Run:

```bash
uvicorn app.main:app --reload
```

The backend will start at:

```text
http://127.0.0.1:8000
```

You can verify that it is running with:

```text
http://127.0.0.1:8000/health
```

---

## 8. Start the Streamlit UI

Open a second terminal.

Activate the virtual environment again if necessary, then run:

```bash
streamlit run streamlit_app.py
```

The Streamlit application will normally open at:

```text
http://localhost:8501
```

---

#  Demo Scenarios

## Demo 1 — Paid Inference

Set the budget to:

```text
$0.05
```

Example flow:

```text
User Task
    ↓
Kiln
    ↓
PAID Recommendation
    ↓
Budget Approved
    ↓
Sepolia Authorization
    ↓
Paid LLM
    ↓
Actual Cost Settlement
    ↓
Final Result
```

The interface displays:

- recommended execution route
- actual execution route
- selected model
- estimated cost
- actual cost
- user charge
- platform charge
- blockchain transaction hash
- input tokens
- output tokens
- final AI response

---

## Demo 2 — Budget-Limited Local Fallback

Set the budget to:

```text
$0
```

When Kiln recommends a paid model:

```text
User Task
    ↓
Kiln
    ↓
PAID Recommendation
    ↓
Budget Rejected
    ↓
qwen3:8b Local Fallback
```

In this case:

```text
Payment Approved : false
Transaction Hash : null
User Charge      : $0
```

The task is executed locally without calling the paid model.

---

# Tech Stack

| Category | Technology |
|---|---|
| Backend | FastAPI |
| Frontend | Streamlit |
| Language | Python 3.11 |
| AI Router | Kiln API |
| Kiln Routing Model | `qwen3-32b` |
| Local Inference | Ollama + `qwen3:8b` |
| Paid Inference | Anthropic Claude |
| Blockchain | Ethereum Sepolia |
| Web3 | Web3.py |
| Validation | Pydantic |
| HTTP Client | httpx |
| Environment | python-dotenv |

---

# Agent Finance

**AI decides what model is needed.  
The user decides how much can be spent.  
The blockchain records the authorization.**

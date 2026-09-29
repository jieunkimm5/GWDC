import json
import os
from pathlib import Path

from dotenv import load_dotenv
from eth_account import Account
from web3 import Web3


# .env 로드
load_dotenv()

RPC_URL = os.getenv("RPC_URL")
PRIVATE_KEY = os.getenv("BLOCKCHAIN_PRIVATE_KEY")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")

if not RPC_URL:
    raise ValueError("RPC_URL is missing in .env")

if not PRIVATE_KEY:
    raise ValueError("BLOCKCHAIN_PRIVATE_KEY is missing in .env")

if not CONTRACT_ADDRESS:
    raise ValueError("CONTRACT_ADDRESS is missing in .env")


# Sepolia 연결
w3 = Web3(Web3.HTTPProvider(RPC_URL))

if not w3.is_connected():
    raise ConnectionError("Failed to connect to blockchain RPC")


# Wallet 로드
account = Account.from_key(PRIVATE_KEY)


# record.py가 있는 폴더 기준으로 ABI 파일 찾기
BASE_DIR = Path(__file__).resolve().parent
ABI_PATH = BASE_DIR / "DecisionRegistry.abi.json"

with open(ABI_PATH, "r", encoding="utf-8") as f:
    abi = json.load(f)


# 이미 배포된 smart contract 연결
contract = w3.eth.contract(
    address=Web3.to_checksum_address(CONTRACT_ADDRESS),
    abi=abi,
)


def record_decision(
    run_id: str,
    decision: str,
    approved: bool,
    amount: str,
    provider: str,
) -> dict:
    """
    AI inference spending decision을 Sepolia smart contract에 기록한다.

    성공 조건:
    - transaction이 block에 포함됨
    - receipt status == 1

    실패 시:
    - RuntimeError 또는 기타 예외 발생
    """

    # Smart contract 함수 호출 transaction 생성
    transaction = contract.functions.recordDecision(
        run_id,
        decision,
        approved,
        amount,
        provider,
    ).build_transaction(
        {
            "from": account.address,
            "nonce": w3.eth.get_transaction_count(
                account.address,
                "pending",
                ),
            "chainId": w3.eth.chain_id,
            "gasPrice": w3.eth.gas_price,
        }
    )

    # 필요한 gas 추정
    transaction["gas"] = w3.eth.estimate_gas(transaction)

    # Private key로 transaction 서명
    signed_tx = account.sign_transaction(transaction)

    # Sepolia network로 transaction 전송
    tx_hash = w3.eth.send_raw_transaction(
        signed_tx.raw_transaction
    )

    # Transaction이 block에 포함될 때까지 기다림
    receipt = w3.eth.wait_for_transaction_receipt(
    tx_hash,
    timeout=300,
    poll_latency=2,
)

    # ★ 가장 중요한 부분
    # Transaction이 실제 성공했을 때만 성공 처리
    if receipt["status"] != 1:
        failed_tx_hash = receipt["transactionHash"].hex()

        if not failed_tx_hash.startswith("0x"):
            failed_tx_hash = "0x" + failed_tx_hash

        raise RuntimeError(
            f"Blockchain transaction failed: {failed_tx_hash}"
        )

    # 성공한 transaction hash
    tx_hash_hex = receipt["transactionHash"].hex()

    if not tx_hash_hex.startswith("0x"):
        tx_hash_hex = "0x" + tx_hash_hex

    return {
        "tx_hash": tx_hash_hex,
        "status": receipt["status"],
        "block_number": receipt["blockNumber"],
    }


if __name__ == "__main__":
    result = record_decision(
        run_id="run_test_001",
        decision="PAID",
        approved=True,
        amount="0.032000",
        provider="paid-model-1",
    )

    print(result)
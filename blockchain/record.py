import os
import json

from dotenv import load_dotenv
from eth_account import Account
from web3 import Web3
from pathlib import Path


load_dotenv()

RPC_URL = os.getenv("RPC_URL")
PRIVATE_KEY = os.getenv("BLOCKCHAIN_PRIVATE_KEY")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")

w3 = Web3(Web3.HTTPProvider(RPC_URL))

account = Account.from_key(PRIVATE_KEY)


BASE_DIR = Path(__file__).resolve().parent
ABI_PATH = BASE_DIR / "DecisionRegistry.abi.json"

with open(ABI_PATH, "r") as f:
    abi = json.load(f)


contract = w3.eth.contract(
    address=Web3.to_checksum_address(CONTRACT_ADDRESS),
    abi=abi
)


def record_decision(
    run_id: str,
    decision: str,
    approved: bool,
    amount: str,
    provider: str
):

    transaction = contract.functions.recordDecision(
        run_id,
        decision,
        approved,
        amount,
        provider
    ).build_transaction({
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address),
        "chainId": w3.eth.chain_id,
        "gasPrice": w3.eth.gas_price,
    })


    transaction["gas"] = w3.eth.estimate_gas(transaction)


    signed_tx = account.sign_transaction(transaction)


    tx_hash = w3.eth.send_raw_transaction(
        signed_tx.raw_transaction
    )


    receipt = w3.eth.wait_for_transaction_receipt(
        tx_hash
    )


    return {
        "tx_hash": receipt.transactionHash.hex(),
        "status": receipt.status,
        "block_number": receipt.blockNumber,
    }


if __name__ == "__main__":

    result = record_decision(
        run_id="run_test_001",
        decision="PAID",
        approved=True,
        amount="0.032000",
        provider="paid-model-1"
    )

    print(result)
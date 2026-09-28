import os
import json

from dotenv import load_dotenv
from eth_account import Account
from solcx import compile_source, set_solc_version
from web3 import Web3


load_dotenv()

RPC_URL = os.getenv("RPC_URL")
PRIVATE_KEY = os.getenv("BLOCKCHAIN_PRIVATE_KEY")

w3 = Web3(Web3.HTTPProvider(RPC_URL))
account = Account.from_key(PRIVATE_KEY)

set_solc_version("0.8.20")


# Solidity 파일 읽기
with open("contracts/DecisionRegistry.sol", "r") as f:
    source = f.read()


# Compile
compiled = compile_source(
    source,
    output_values=["abi", "bin"]
)

contract_id, contract_interface = compiled.popitem()

abi = contract_interface["abi"]
bytecode = contract_interface["bin"]


# ABI 저장
with open("blockchain/DecisionRegistry.abi.json", "w") as f:
    json.dump(abi, f)


# Contract 객체 생성
DecisionRegistry = w3.eth.contract(
    abi=abi,
    bytecode=bytecode
)


# Deploy transaction 생성
transaction = DecisionRegistry.constructor().build_transaction({
    "from": account.address,
    "nonce": w3.eth.get_transaction_count(account.address),
    "chainId": w3.eth.chain_id,
    "gasPrice": w3.eth.gas_price,
})


# 필요한 gas 계산
transaction["gas"] = w3.eth.estimate_gas(transaction)


# Private key로 서명
signed_tx = account.sign_transaction(transaction)


# Sepolia로 전송
tx_hash = w3.eth.send_raw_transaction(
    signed_tx.raw_transaction
)

print("Deploy TX Hash:", tx_hash.hex())
print("Waiting for confirmation...")


# block에 포함될 때까지 기다림
receipt = w3.eth.wait_for_transaction_receipt(tx_hash)


print("Contract deployed!")
print("Contract Address:", receipt.contractAddress)
print("Block Number:", receipt.blockNumber)
print("Status:", receipt.status)
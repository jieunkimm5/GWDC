import os
import json

from dotenv import load_dotenv
from web3 import Web3


load_dotenv()

RPC_URL = os.getenv("RPC_URL")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")

w3 = Web3(Web3.HTTPProvider(RPC_URL))


with open("blockchain/DecisionRegistry.abi.json", "r") as f:
    abi = json.load(f)


contract = w3.eth.contract(
    address=Web3.to_checksum_address(CONTRACT_ADDRESS),
    abi=abi
)


record = contract.functions.getRecord(
    "run_test_001"
).call()


print("run_id:", record[0])
print("decision:", record[1])
print("approved:", record[2])
print("amount:", record[3])
print("provider:", record[4])
print("timestamp:", record[5])
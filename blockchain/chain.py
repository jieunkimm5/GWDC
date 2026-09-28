import os

from dotenv import load_dotenv
from eth_account import Account
from web3 import Web3


load_dotenv()

RPC_URL = os.getenv("RPC_URL")
PRIVATE_KEY = os.getenv("BLOCKCHAIN_PRIVATE_KEY")

if not RPC_URL:
    raise ValueError("RPC_URL is missing in .env")

if not PRIVATE_KEY:
    raise ValueError("BLOCKCHAIN_PRIVATE_KEY is missing in .env")


w3 = Web3(Web3.HTTPProvider(RPC_URL))
account = Account.from_key(PRIVATE_KEY)

print("Connected:", w3.is_connected())

if w3.is_connected():
    print("Chain ID:", w3.eth.chain_id)
    print("Wallet address:", account.address)

    balance_wei = w3.eth.get_balance(account.address)
    balance_eth = w3.from_wei(balance_wei, "ether")

    print("Balance:", balance_eth, "ETH")
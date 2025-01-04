import json
import random
import time
import sys
from typing import List
from web3 import Web3
from web3.middleware import geth_poa_middleware
from dotenv import load_dotenv
import os
import logging
from colorama import init, Fore, Style

# Initialize colorama
init(autoreset=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger()

def log_info(message: str):
    logger.info(f"{Fore.BLUE}{message}{Style.RESET_ALL}")

def log_success(message: str):
    logger.info(f"{Fore.GREEN}{message}{Style.RESET_ALL}")

def log_error(message: str):
    logger.error(f"{Fore.RED}{message}{Style.RESET_ALL}")

def prompt_user(question: str) -> int:
    while True:
        try:
            answer = input(f"{Fore.CYAN}{question}{Style.RESET_ALL}")
            return int(answer)
        except ValueError:
            log_error("Please enter a valid integer.")

def delay(seconds: float):
    time.sleep(seconds)

def load_private_keys() -> List[str]:
    private_keys = os.getenv('PRIVATE_KEY')
    if not private_keys:
        raise ValueError('PRIVATE_KEY not set in .env file')
    try:
        keys = json.loads(private_keys)
        if not isinstance(keys, list):
            raise ValueError('PRIVATE_KEY should be a JSON list of keys')
        return keys
    except json.JSONDecodeError:
        raise ValueError('PRIVATE_KEY is not a valid JSON list')

def transfer_eth():
    # Load environment variables
    load_dotenv()

    rpc_url = os.getenv('RPC_URL')
    chain_id = os.getenv('CHAIN_ID')

    if not rpc_url:
        raise ValueError('RPC_URL not set in .env file')
    if not chain_id:
        raise ValueError('CHAIN_ID not set in .env file')
    try:
        chain_id = int(chain_id)
    except ValueError:
        raise ValueError('CHAIN_ID must be an integer')

    # Initialize Web3
    web3 = Web3(Web3.HTTPProvider(rpc_url))

    # If you're connecting to a testnet or private network that uses PoA, uncomment the next line
    # web3.middleware_onion.inject(geth_poa_middleware, layer=0)

    if not web3.is_connected():
        log_error("Failed to connect to the Ethereum node.")
        sys.exit(1)
    else:
        log_success("Successfully connected to the Ethereum node.")

    num_transactions = prompt_user('How many transactions, for example 100: ')

    private_keys = load_private_keys()

    for key in private_keys:
        try:
            account = web3.eth.account.from_key(key)
        except ValueError:
            log_error(f"Invalid private key: {key}")
            continue

        wallet_address = account.address
        balance = web3.eth.get_balance(wallet_address)
        eth_balance = web3.from_wei(balance, 'ether')
        log_info(f"Current ETH balance of {wallet_address}: {eth_balance} ETH")

        if balance == 0:
            log_error(f"Wallet {wallet_address} has zero balance. Skipping...")
            continue

        nonce = web3.eth.get_transaction_count(wallet_address, 'pending')
        success_count = 0

        for _ in range(num_transactions):
            recipient = Web3().eth.account.create().address
            amount = random.uniform(0.0000001, 0.000001)  # Amount in ETH
            gas_price = web3.eth.gas_price + web3.to_wei(1, 'gwei')

            tx = {
                'chainId': chain_id,
                'from': wallet_address,
                'to': recipient,
                'value': web3.to_wei(amount, 'ether'),
                'gasPrice': gas_price,
                'nonce': nonce
            }

            try:
                gas_limit = web3.eth.estimate_gas(tx)
                total_cost = web3.to_wei(amount, 'ether') + (gas_limit * gas_price)

                if balance < total_cost:
                    log_error(
                        f"[+] Insufficient balance: required {web3.from_wei(total_cost, 'ether')} ETH, but available {web3.from_wei(balance, 'ether')} ETH"
                    )
                    break

                tx['gas'] = gas_limit
                signed_tx = web3.eth.account.sign_transaction(tx, key)
                tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)

                tx_receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
                if tx_receipt.status == 1:
                    success_count += 1
                    log_success(f"Transaction successful with hash: {tx_hash.hex()}")
                    nonce += 1
                else:
                    log_error("Transaction failed.")

            except ValueError as e:
                if 'replacement transaction underpriced' in str(e):
                    gas_price += web3.to_wei(2, 'gwei')  # Increment gas price
                    tx['gasPrice'] = gas_price
                    signed_tx = web3.eth.account.sign_transaction(tx, key)
                    tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
                    log_success(f"Retried transaction successful with hash: {tx_hash.hex()}")
                    nonce += 1
                else:
                    log_error(f"Transaction error: {str(e)}")
            except Exception as e:
                log_error(f"Unexpected error: {str(e)}")
                break

        log_info(f"Completed transfers from wallet {wallet_address}. Successful transactions: {success_count}")

if __name__ == "__main__":
    try:
        transfer_eth()
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        sys.exit(1)

import json, os, pathlib
from web3 import Web3
from dotenv import load_dotenv

ROOT = pathlib.Path(__file__).resolve().parents[1]
load_dotenv(ROOT/"python"/".env")
w3 = Web3(Web3.HTTPProvider(os.environ["RPC_URL"]))
acct = w3.eth.account.from_key(os.environ["PRIVATE_KEY"])

abi = json.loads((ROOT/"python"/"deployed"/"FirmwareRegistry.abi.json").read_text())
bytecode = (ROOT/"python"/"deployed"/"FirmwareRegistry.bin").read_text()

Firmware = w3.eth.contract(abi=abi, bytecode=bytecode)

# Estimate gas for constructor
gas_est = Firmware.constructor().estimate_gas({'from': acct.address})

# EIP-1559 fees (Ganache shows baseFee even on dev chains)
base_fee = w3.eth.get_block('latest')['baseFeePerGas']
max_priority = w3.to_wei(1, 'gwei')
max_fee = base_fee + max_priority

tx  = Firmware.constructor().build_transaction({
    "from": acct.address,
    "nonce": w3.eth.get_transaction_count(acct.address),
    "chainId": w3.eth.chain_id,           # 1337 in your logs
    "gas": int(gas_est) + 100000,         # cushion
    "maxFeePerGas": max_fee,
    "maxPriorityFeePerGas": max_priority,
})

signed = acct.sign_transaction(tx)
txh = w3.eth.send_raw_transaction(signed.raw_transaction)  # <-- snake_case
rcpt = w3.eth.wait_for_transaction_receipt(txh)

(ROOT/"python"/"deployed"/"FirmwareRegistry.address").write_text(rcpt.contractAddress)
print("Deployed FirmwareRegistry at:", rcpt.contractAddress)

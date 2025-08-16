import os, json, pathlib, hashlib, sys
from web3 import Web3
from dotenv import load_dotenv

ROOT = pathlib.Path.home() / "ota-chain"
DEP  = ROOT / "python" / "deployed"
load_dotenv(ROOT / "python" / ".env")

w3   = Web3(Web3.HTTPProvider(os.environ["RPC_URL"]))
acct = w3.eth.account.from_key(os.environ["PRIVATE_KEY"])

abi  = json.loads((DEP/"FirmwareRegistry.abi.json").read_text())
addr = (DEP/"FirmwareRegistry.address").read_text().strip()
reg  = w3.eth.contract(address=addr, abi=abi)

device_type = "esp32-s3"
cid         = "QmSUhm9QaZ1d8uk5ALGoagYH6czCkXfH6Zy4Kzd5rnfW5t"

# Use a shorter on-chain URI to save gas; your ESP can translate ipfs:// to HTTPS later.
uri         = f"ipfs://{cid}"

# Show basic chain info
print("Chain ID:", w3.eth.chain_id)
print("Account:", acct.address, "Balance(ETH):", w3.from_wei(w3.eth.get_balance(acct.address),'ether'))

# Current version -> target version
current = reg.functions.latestVersion(device_type).call()
target_version = current + 1
print(f"latestVersion[{device_type}] = {current} → publishing v{target_version}")

# Hash the exact file you added to IPFS
bin_path = "/var/lib/ipfs/hello.txt"
h = hashlib.sha256()
with open(bin_path, "rb") as f:
    h.update(f.read())
sha_bytes = h.digest()               # bytes32
sha_hex   = "0x" + h.hexdigest()
print("SHA-256:", sha_hex)

# Build tx with EIP-1559 fees and robust gas sizing
base = w3.eth.get_block('latest').get('baseFeePerGas', 0)
prio = w3.to_wei(1, 'gwei')
max_fee = (base + prio) if base else w3.to_wei(2, 'gwei')

try:
    gas_est = reg.functions.publish(device_type, target_version, uri, sha_bytes)\
               .estimate_gas({'from': acct.address})
    gas = int(gas_est * 2)          # generous pad
    print("estimate_gas:", gas_est, "→ using", gas)
except Exception as e:
    print("estimate_gas failed:", e, "→ fallback gas 2,000,000")
    gas = 2_000_000

tx = reg.functions.publish(device_type, target_version, uri, sha_bytes).build_transaction({
    "from": acct.address,
    "nonce": w3.eth.get_transaction_count(acct.address),
    "chainId": w3.eth.chain_id,
    "gas": gas,
    "maxFeePerGas": max_fee,
    "maxPriorityFeePerGas": prio,
})

signed = acct.sign_transaction(tx)
txh = w3.eth.send_raw_transaction(signed.raw_transaction)   # web3.py uses snake_case
rcpt = w3.eth.wait_for_transaction_receipt(txh)

print("tx:", txh.hex())
print("status:", rcpt.status, "gasUsed:", rcpt.gasUsed)
if rcpt.status != 1:
    print("❌ Publish failed (status 0). Stop here.")
    sys.exit(1)

# Read back latest
(version, out_uri, out_sha) = reg.functions.getLatest(device_type).call()
print("LATEST →", version, out_uri, Web3.to_hex(out_sha))

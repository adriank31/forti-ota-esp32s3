import os, json, pathlib
from flask import Flask, request, jsonify
from web3 import Web3
from dotenv import load_dotenv

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEPLOYED = ROOT/"python"/"deployed"
load_dotenv(ROOT/"python"/".env")

w3 = Web3(Web3.HTTPProvider(os.environ["RPC_URL"]))
acct = w3.eth.account.from_key(os.environ["PRIVATE_KEY"])

abi  = json.loads((DEPLOYED/"FirmwareRegistry.abi.json").read_text())
addr = (DEPLOYED/"FirmwareRegistry.address").read_text().strip()
reg  = w3.eth.contract(address=addr, abi=abi)

def _fees():
    base = w3.eth.get_block('latest')['baseFeePerGas']
    prio = w3.to_wei(1, 'gwei')
    return base + prio, prio

app = Flask(__name__)

@app.get("/firmware/latest")
def latest():
    device_type = request.args.get("deviceType","esp32-s3")
    (version, uri, sha256sum) = reg.functions.getLatest(device_type).call()
    return jsonify({"deviceType": device_type, "version": int(version), "uri": uri, "sha256": Web3.to_hex(sha256sum)})

@app.post("/ack")
def ack():
    p = request.get_json(force=True)
    device_id   = p.get("deviceId","unknown")
    device_type = p.get("deviceType","esp32-s3")
    version     = int(p.get("version",0))
    success     = bool(p.get("success",False))
    info        = p.get("info","")
    gas_est = reg.functions.ack(device_id, device_type, version, success, info)\
              .estimate_gas({'from': acct.address})
    max_fee, max_prio = _fees()
    tx = reg.functions.ack(device_id, device_type, version, success, info).build_transaction({
        "from": acct.address,
        "nonce": w3.eth.get_transaction_count(acct.address),
        "chainId": w3.eth.chain_id,
        "gas": int(gas_est) + 50000,
        "maxFeePerGas": max_fee,
        "maxPriorityFeePerGas": max_prio,
    })
    signed = acct.sign_transaction(tx)
    txh = w3.eth.send_raw_transaction(signed.raw_transaction)
    rcpt = w3.eth.wait_for_transaction_receipt(txh)
    return jsonify({"status":"ok","tx": rcpt.transactionHash.hex()})
    
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050)

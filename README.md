# ESP32-S3 OTA via HTTPS + IPFS with an On-Chain Registry (Raspberry Pi gateway)

## Why I built this

I wanted a **local, trustable, reproducible OTA pipeline** for ESP32 devices that doesn’t depend on a third-party cloud. My goals:

* Host firmware **on IPFS** (content-addressed with a CID).
* Serve downloads **over HTTPS** from my own **Raspberry Pi** (with my own root CA).
* Keep a **registry of latest firmware per device type on chain** (local Ganache devnet).
* Provide a simple **gateway API** the device can query for “latest” and optionally **ACK** back after a successful update.

The ESP32 client uses Espressif’s `esp_https_ota` update flow (the “advanced\_https\_ota” example) and validates TLS using my own CA that I embed in the firmware.

---

## High-level architecture

* **Kubo (IPFS)** on the Pi stores the `.bin` image; I add it via the **HTTP API** and use the **Gateway** path `/ipfs/<CID>` to serve it.
* **Nginx** terminates TLS for `https://forti-ota-pi.local/` and reverse-proxies:

  * `/firmware/*` and `/ack` → local **Flask** gateway on `127.0.0.1:5050`
  * everything else (not `/api/v0`) → **Kubo Gateway** on `127.0.0.1:8080`
    (I block direct access to the Kubo **RPC API** path for safety.)
* **Flask gateway** exposes:

  * `GET /firmware/latest?deviceType=esp32-s3` → latest metadata from the chain
  * `POST /ack` → optional “I updated” write-back to the chain
    (Flask’s built-in server is fine behind Nginx for my lab; production should use a WSGI server.)
* **Ganache** provides a local Ethereum devchain; I deploy a `FirmwareRegistry` contract and publish (deviceType, version, sha256, ipfsURI). I talk to Ganache using **web3.py** with EIP-1559 style tx fields.
* **ESP32-S3** runs the **advanced HTTPS OTA** example; it embeds my Pi’s **root CA** and downloads from `https://forti-ota-pi.local/ipfs/<CID>`.

---

## Hardware & OS I used

* ESP32-S3-N16R8 dev board (USB-to-UART bridge = **CP210x**; Windows driver here).
* Raspberry Pi 4 (64-bit), Ethernet to my home router.
* My Windows laptop with **ESP-IDF 5.4.x** and **VS Code**.

---

## Software I installed

**On the Raspberry Pi**

* **Kubo (IPFS)**

  * I run the daemon with the HTTP API on `127.0.0.1:5001` and the Gateway on `127.0.0.1:8080`.
  * I use the HTTP API to `add` firmware (`/api/v0/add`).
* **Nginx** (TLS termination & reverse proxy).
* **Node.js + solc** (to compile my Solidity contract).
* **Ganache** (local Ethereum chain).
* **Python (venv)** with `flask`, `web3`, etc. (for the gateway and deployment scripts).
* **systemd** services for Ganache and the Flask gateway (so they survive reboots).

**On Windows (for ESP32 development)**

* **ESP-IDF 5.4.x** + toolchains + VS Code.
* **CP210x USB-to-UART** driver (for the board’s serial).

---

## My repo layout (server side)

```
ota-chain/
  contracts/           # FirmwareRegistry.sol
  jsbuild/
    compile.js         # solc compile -> ABI+BIN artifacts
    package.json
  python/
    deployed/          # ABI & BIN outputs
    deploy_from_artifacts.py
    publish_v1_retry.py
    gateway.py         # Flask app: /firmware/latest and /ack
  ...
/etc/nginx/sites-available/ipfs-https  # my vhost with TLS & proxies
/etc/ssl/ipfs/                         # rootCA.pem, server.crt, server.key
```

---

## Step-by-step: Raspberry Pi setup

### 1) Kubo (IPFS)

Install Kubo, then initialize and run the daemon. I use the HTTP API to add firmware and the Gateway to serve `/ipfs/<CID>`.

Add a firmware binary (later I’ll point the ESP32 to this CID):

```bash
curl -s -X POST -F file=@/home/adrian/advanced_https_ota.bin \
  'http://127.0.0.1:5001/api/v0/add?cid-version=1&pin=true'
# -> {"Name":"advanced_https_ota.bin","Hash":"bafy...","Size":"..."}
```

Verify I can fetch via the local Gateway:

```bash
CID=bafy...   # returned Hash
curl --cacert /etc/ssl/ipfs/rootCA.pem \
  "https://forti-ota-pi.local/ipfs/$CID" -o /tmp/fw.bin
sha256sum /tmp/fw.bin /home/adrian/advanced_https_ota.bin
```

(HTTP API “add” endpoint and Gateway behavior are documented here.)

### 2) Nginx TLS reverse proxy

I terminate TLS at Nginx and proxy to Flask and Kubo:

```nginx
server {
  listen 443 ssl;
  server_name forti-ota-pi.local 192.168.1.167;

  ssl_certificate     /etc/ssl/ipfs/server.crt;
  ssl_certificate_key /etc/ssl/ipfs/server.key;
  ssl_protocols TLSv1.2 TLSv1.3;

  # Block Kubo RPC API
  location /api/v0/ { return 403; }

  # Gateway JSON (Flask on 127.0.0.1:5050)
  location /firmware/ { proxy_pass http://127.0.0.1:5050/firmware/; }
  location /ack      { proxy_pass http://127.0.0.1:5050/ack; }

  # Everything else -> Kubo Gateway
  location / {
    proxy_pass http://127.0.0.1:8080;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $remote_addr;
  }
}
server {
  listen 80;
  server_name forti-ota-pi.local 192.168.1.167;
  return 301 https://$host$request_uri;
}
```

(Proxied upstreams with `proxy_pass` are standard Nginx; Flask warns its built-in server isn’t for production, which is why I place it behind Nginx here.)

### 3) Ganache (local chain) + contract

Start Ganache as a service (port `8545`). Then compile & deploy the `FirmwareRegistry`:

```bash
# Node compile step (solc)
cd ~/ota-chain/jsbuild && node compile.js

# Python deploy
python ~/ota-chain/python/deploy_from_artifacts.py
# -> Deployed FirmwareRegistry at: 0x...
```

Ganache gives me deterministic dev accounts and fast blocks for local testing. ([Home Assistant Community][7])

### 4) Publish firmware metadata to the chain

I publish `(deviceType, version, sha256, ipfsURI)` using web3.py:

```bash
python ~/ota-chain/python/publish_v1_retry.py
# example output:
# Chain ID: 1337
# latestVersion[esp32-s3] = 0 → publishing v1
# SHA-256: 0x4f9d7a...
# LATEST → 1 ipfs://bafy... 0x4f9d7a...
```

(Using web3.py with EIP-1559 style gas fields is the modern approach.) ([PlatformIO Community][8])

### 5) Flask gateway as a service

I run the Flask app under systemd so it’s always up:

```
[Unit]
Description=OTA Gateway (Flask -> Ganache)
After=network-online.target
Wants=network-online.target

[Service]
User=adrian
WorkingDirectory=/home/adrian/ota-chain/python
Environment="PATH=/home/adrian/otaenv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin"
ExecStart=/home/adrian/otaenv/bin/python /home/adrian/ota-chain/python/gateway.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Quick check:

```bash
curl --cacert /etc/ssl/ipfs/rootCA.pem \
  "https://forti-ota-pi.local/firmware/latest?deviceType=esp32-s3"
# -> {"deviceType":"esp32-s3","version":1,"uri":"ipfs://...","sha256":"0x..."}
```

---

## Step-by-step: ESP32-S3 client (ESP-IDF)

I started from `protocols/ota/advanced_https_ota` and made three key changes:

1. **Embed my Pi’s root CA** (so TLS validates my Nginx cert):

* Copied the file to my project at
  `advanced_https_ota/server_certs/ca_cert.pem`
* In `main/CMakeLists.txt` I embed it:

```cmake
idf_component_register(SRCS "advanced_https_ota_example.c" "ble_helper/bluedroid_gatts.c" "ble_helper/nimble_gatts.c" "ble_helper/ble_api.c"
  INCLUDE_DIRS "." "./ble_helper/include/"
  EMBED_TXTFILES ${project_dir}/server_certs/ca_cert.pem)
```

The example references it via the linker symbols
`_binary_ca_cert_pem_start/_end`. (This is the standard pattern for `esp_https_ota` examples.)

2. **Point the firmware URL to IPFS via my host name**

In **menuconfig**:

* `Example Connection Configuration` → set my **Wi-Fi SSID/Password** (this comes from `protocol_examples_common`).
* `Example Configuration` → **Firmware upgrade URL** =
  `https://forti-ota-pi.local/ipfs/<CID>`
  (Use the IPFS **Gateway** path `/ipfs/<CID>`, not the API path.)

3. **Build, flash, monitor**

```powershell
idf.py set-target esp32s3
idf.py -p COM9 build
idf.py -p COM9 erase-flash
idf.py -p COM9 flash monitor
```

On first boot, I see Wi-Fi connect, then `esp_https_ota` downloads to `ota_0`, validates, switches the boot partition, and reboots into the new image. (The `esp_https_ota` APIs & flow are documented here.)

> If Windows didn’t talk to the board initially, I installed the **CP210x VCP** driver.

---

## Publishing a new firmware (v2, v3, …)

1. Rebuild the app → `build/advanced_https_ota.bin`
2. Add it to IPFS on the Pi to get a new CID:

```bash
curl -s -X POST -F file=@/home/adrian/advanced_https_ota.bin \
  'http://127.0.0.1:5001/api/v0/add?cid-version=1&pin=true'
```


3. Run my publish script to bump the on-chain version and store the new `(CID, sha256)`.
4. Devices running the app check on boot (this example does a single check at startup), download over **HTTPS**, validate, flash, and reboot.

---

## Optional: On-chain ACK after update

I also exposed `POST /ack` on the Flask gateway (so a device or a script can report success):

```bash
curl -H "Content-Type: application/json" \
  -d '{"deviceId":"esp-01","deviceType":"esp32-s3","version":1,"success":true,"info":"hello"}' \
  https://forti-ota-pi.local/ack
# -> {"status":"ok","tx":"0x..."}
```

(Integrating this into the ESP app is straightforward with `esp_http_client` if I want it automatic.)

---

## Security notes & gotchas

* **Do not expose** Kubo’s `/api/v0/*` RPC API publicly; keep it bound to `127.0.0.1` or firewall it. (I block it at Nginx too.)
* Use a **hostname** (`forti-ota-pi.local`) that matches your Nginx cert’s CN/SAN so TLS validation passes.
* Don’t commit **private keys** or **root CA** materials to GitHub.
* Flask’s dev server is fine behind Nginx in my lab; for production, use a proper WSGI server (gunicorn/uwsgi) as Flask documents.
* Ganache is a **dev chain**; never reuse those keys/funds on mainnet.

---

## What’s in this repository

* `advanced_https_ota/` — my ESP-IDF app (with `server_certs/ca_cert.pem` embedded).
* `ota-chain/` — contract, compile script, Python deploy/publish scripts, gateway.
* `docs/` — screenshots (17 images) and a short demo video of `idf.py build/flash/monitor`.
  *(Put your images/video here; I kept filenames simple like `01-ganache.png`, `02-ipfs-add.png`, …, and `demo.mp4`.)*

---

## How to run this end-to-end (quick checklist)

1. **Pi**: Start Kubo, Ganache, and the Flask gateway services; make sure Nginx TLS proxy is active.
2. **Build ESP32**: `idf.py -p COMx build flash monitor` (with Wi-Fi + URL set).
3. **Publish**: `curl /api/v0/add` the new `.bin` → get CID → run my `publish_vX_retry.py`.
4. **Device**: Reboot → the app runs `esp_https_ota`, downloads from `https://forti-ota-pi.local/ipfs/<CID>`, validates, flashes, reboots.

---

## Acknowledgments

* Espressif **ESP-IDF** and the **advanced\_https\_ota** example + `esp_https_ota` APIs.
* **Kubo (IPFS)** HTTP API & Gateway.
* **Ganache** for the local chain and **web3.py** for easy deployment/tx.
* **Nginx** docs for proxying/upstreams.

---

## License

This repo documents my lab setup and includes example code. The ESP-IDF example files remain under Espressif’s original licensing terms.

---

### Appendix: Handy links

* Wi-Fi OTA example overview (esp-idf docs). 
* `esp_https_ota` API reference.
* Kubo **HTTP API** (`/api/v0/add`).
* IPFS **Gateway** path semantics (`/ipfs/<CID>`). 
* Nginx `proxy_pass` reference. 
* Flask deployment warning. 
* Ganache (local blockchain). 
* web3.py (transactions / EIP-1559).
* CP210x VCP drivers.

---

### What worked for me (my verified run)

* Contract deployed to Ganache; `publish_v1_retry.py` set `esp32-s3` → **v1** with SHA-256 and IPFS URI.
* `GET /firmware/latest?deviceType=esp32-s3` returned JSON with version/CID from Flask.
* ESP32 connected to Wi-Fi, downloaded from `https://forti-ota-pi.local/ipfs/<CID>`, verified, flashed, **rebooted into the new image**.
* Optional: I posted an `ACK` via `POST /ack` and received a tx hash back.

If you follow this README top-to-bottom you’ll reproduce the same result in your own lab.

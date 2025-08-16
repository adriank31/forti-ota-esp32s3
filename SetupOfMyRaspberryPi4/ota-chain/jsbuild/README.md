# `jsbuild/` — Solidity compiler helper

This folder holds a tiny Node.js helper that compiles `contracts/FirmwareRegistry.sol` and drops the build artifacts (ABI + bytecode) into `../python/deployed/` for the Python scripts to deploy and interact with.

## Why there’s no `node_modules/` in Git

`node_modules/` is huge and platform-specific. We don’t commit it. Instead, we commit the exact dependency recipe (`package.json` + `package-lock.json`) and anyone can recreate `node_modules/` locally in a few seconds with `npm ci`.

> If you see this directory without `node_modules/`, that’s expected.

## Requirements

* **Node.js**: LTS (v18+ recommended).
  Check:

  ```bash
  node -v
  npm -v
  ```
* **npm**: Use the one that ships with your Node.js install.

## What gets installed here

* **solc** — the Solidity compiler (JavaScript/wasm build).
  We use it programmatically from `compile.js` to compile `FirmwareRegistry.sol` with optimizer and `evmVersion: "paris"` to avoid Shanghai-only opcodes.

Nothing else is required for this folder. (`fs` is built into Node.)

## Install

From this `jsbuild/` directory:

```bash
# Recreate node_modules exactly from package-lock.json (preferred for CI/repeatable builds)
npm ci

# If you’re adding/updating deps locally (developers only), use:
# npm install
```

If you don’t have a `package-lock.json` yet, `npm ci` will refuse to run; use `npm install` once to produce it, then commit both `package.json` and `package-lock.json`.

## Build (compile the contract)

```bash
node compile.js
```

On success, you should see:

```
Artifacts written to ../python/deployed
```

And these files will appear:

```
../python/deployed/FirmwareRegistry.abi.json
../python/deployed/FirmwareRegistry.bin
```

## Typical workflow

1. Edit `contracts/FirmwareRegistry.sol`.
2. Run `node compile.js` (or `npm run build`, see below).
3. Switch to `../python/` and run your deployment/publish scripts.

## NPM scripts (optional but handy)

You can add this to `package.json` to make commands nicer:

```json
{
  "name": "ota-chain-jsbuild",
  "private": true,
  "type": "module",
  "scripts": {
    "build": "node compile.js",
    "clean": "rimraf ../python/deployed && mkdir -p ../python/deployed"
  },
  "dependencies": {
    "solc": "^0.8.26"
  }
}
```

Then:

```bash
npm ci
npm run build
```

> If your Solidity pragma is different (e.g. `pragma solidity ^0.8.20;`), set `solc` to a matching major.minor (e.g. `^0.8.20`). The JS compiler covers the whole 0.8.x line, but matching is a good habit.

## .gitignore (what to keep out of Git)

At the repo root (or in this folder), make sure you ignore the build output and the dependency cache:

```
ota-chain/jsbuild/node_modules/
ota-chain/jsbuild/.npm/
```

(You should already be ignoring `node_modules/` globally; the official Node.gitignore template does this.)

## Troubleshooting

* **`node compile.js` fails with a version error**
  Ensure `solc` version aligns with your contract pragma and you’re compiling with `evmVersion: "paris"` (that’s set in `compile.js` already).

* **`npm ci` refuses to run**
  That means there’s no `package-lock.json` or it’s out of sync. Run `npm install` once to create/update the lockfile, commit it, then use `npm ci` going forward.

* **Artifacts don’t appear in `../python/deployed/`**
  Re-check that you’re running the command from `jsbuild/` and that `contracts/FirmwareRegistry.sol` exists. The script writes to `../python/deployed/` relative to this folder.

---

### Two quick references

* Node.js downloads (choose an LTS build)
* npm CLI docs (general usage, running package commands)


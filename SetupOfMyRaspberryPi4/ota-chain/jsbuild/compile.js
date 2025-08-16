const fs = require('fs');
const solc = require('solc');

const src = fs.readFileSync('../contracts/FirmwareRegistry.sol','utf8');
const input = {
  language: 'Solidity',
  sources: { 'FirmwareRegistry.sol': { content: src } },
  settings: {
    optimizer: { enabled: true, runs: 200 },
    evmVersion: 'paris',            // <-- avoid PUSH0 (Shanghai)
    outputSelection: { '*': { '*': ['abi','evm.bytecode.object'] } }
  }
};
const out = JSON.parse(solc.compile(JSON.stringify(input)));
if (out.errors) {
  for (const e of out.errors) console.error(e.formattedMessage || e.message);
  if (out.errors.some(e => e.severity === 'error')) process.exit(1);
}
const c = out.contracts['FirmwareRegistry.sol']['FirmwareRegistry'];
fs.mkdirSync('../python/deployed', { recursive: true });
fs.writeFileSync('../python/deployed/FirmwareRegistry.abi.json', JSON.stringify(c.abi, null, 2));
fs.writeFileSync('../python/deployed/FirmwareRegistry.bin', c.evm.bytecode.object);
console.log("Artifacts written to ../python/deployed");

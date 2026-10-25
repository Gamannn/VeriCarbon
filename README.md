# VeriCarbon

AI-powered MRV + cross-registry verification for forest-restoration carbon credits.
Submission for the IEEE ClimateChain Global Hackathon 2026, Track 1
("Carbon Markets and Emissions Transparency").

VeriCarbon answers two questions a carbon-credit buyer actually cares about:

1. **Does the environmental evidence support the claimed restoration area?**
   The pipeline fetches Sentinel-2 L2A scenes, computes NDVI inside the project
   polygon, and reports a vegetated-area estimate with an explicit confidence
   score. The exact scene list, model code, and output are committed to the
   blockchain as three hashes, so the result is reproducible bit-for-bit.
2. **Has the same land already been claimed somewhere else?**
   The project polygon is converted to [H3](https://h3geo.org) resolution-9
   cells. The smart contract keeps a map of `cell → active project`. Any
   second submission that touches an already-claimed cell is reverted at the
   contract level, **regardless of the project name, legal entity, or
   registry it is submitted under.**

See [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) for the full system diagram.

## Status

| Component | State |
|---|---|
| Smart contract (`contracts/src/VeriCarbon.sol`) | ✅ compiles, 22 tests passing (incl. 256-run fuzz) |
| Satellite verification pipeline | ✅ fixture mode wired, live mode implemented but not run automatically |
| Entity-resolution + duplicate scoring | ✅ 5 tests passing on hand-crafted cases |
| Backend API (FastAPI + web3.py) | ✅ 6 tests passing; integration against local anvil verified |
| Frontend dashboard | ✅ single-file React page with Leaflet map, calling the real backend |
| End-to-end scenarios A + B | ✅ run against local anvil, outputs committed to `docs/demo_run.json` |
| Sepolia testnet deployment | ✅ live at [`0x7CA4fa4da03c443d188e1E8D35ec1aDfA5090Ec6`](https://sepolia.etherscan.io/address/0x7CA4fa4da03c443d188e1E8D35ec1aDfA5090Ec6), Etherscan-verified, both scenarios run on-chain — see [`docs/DEPLOYMENT.md`](./docs/DEPLOYMENT.md) |
| Slither static analysis | ✅ clean on our source after dismissing false positives on enum comparisons — [`docs/slither_report.txt`](./docs/slither_report.txt) |
| Demo video | ⏳ outline in `docs/DEMO_VIDEO.md` |

Honest limitations are collected in [`docs/KNOWN_LIMITATIONS.md`](./docs/KNOWN_LIMITATIONS.md).

## Repository layout

```
contracts/      Foundry project: VeriCarbon.sol, tests, deploy script
pipeline/       Python: geospatial, satellite verification, entity resolution
backend/        FastAPI service: wires pipeline + web3.py
frontend/       Single-page React dashboard (CDN, no build step)
scripts/        run_scenarios.py — end-to-end demo against a live chain
docs/           Architecture, security, climate impact, limitations, eval report
```

## Quick start (local, 5 minutes)

Prerequisites: Foundry (`forge`, `anvil`), Python 3.12, Node 18+ (only if you
want a static server; `python -m http.server` works too).

```bash
# 1. Clone and install
git clone <this-repo> VeriCarbon && cd VeriCarbon
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd contracts && forge install OpenZeppelin/openzeppelin-contracts && cd ..

# 2. Smart contract tests
cd contracts && forge test -vv && cd ..

# 3. Pipeline + backend tests
pytest pipeline/tests backend/tests -v

# 4. End-to-end against a local chain
anvil &
cd contracts && \
  PRIVATE_KEY=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80 \
  EXTRA_VALIDATOR=0x70997970C51812dc3A010C7d01b50e0d17dc79C8 \
  forge script script/Deploy.s.sol --rpc-url http://127.0.0.1:8545 --broadcast
cd ..
RPC_URL=http://127.0.0.1:8545 \
CONTRACT_ADDRESS=0x5FbDB2315678afecb367f032d93F642f64180aa3 \
BACKEND_PRIVATE_KEY=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80 \
VALIDATOR2_PRIVATE_KEY=0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d \
CHAIN_ID=31337 \
python scripts/run_scenarios.py

# 5. Backend + dashboard
RPC_URL=http://127.0.0.1:8545 \
CONTRACT_ADDRESS=0x5FbDB2315678afecb367f032d93F642f64180aa3 \
BACKEND_PRIVATE_KEY=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80 \
CHAIN_ID=31337 \
uvicorn backend.app:app --port 8000 &
python -m http.server --directory frontend 5173
# open http://127.0.0.1:5173
```

The anvil private keys above are the deterministic default accounts and are
**not** real funds. Never put a key with real value in a shell history.

## Deploy to Sepolia

```bash
cd contracts
cp .env.example .env   # edit: PRIVATE_KEY, SEPOLIA_RPC_URL
source .env
forge script script/Deploy.s.sol \
  --rpc-url $SEPOLIA_RPC_URL \
  --broadcast \
  --verify  # optional, needs ETHERSCAN_API_KEY
```

## Not a replacement for an accredited registry

VeriCarbon does not quantify tonnes of CO₂, does not address additionality,
permanence, or leakage, and is not a substitute for Verra, Gold Standard, or
any accredited MRV provider. It is **integrity infrastructure** aimed at the
cross-registry double-counting and reproducibility problems.

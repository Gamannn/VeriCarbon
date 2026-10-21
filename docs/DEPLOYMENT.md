# Sepolia Deployment

Live, verified deployment of the VeriCarbon contract on Ethereum Sepolia.
Every hash below is reproducible — click any one to open its Etherscan page.

## Contract

| | |
|---|---|
| **Address** | [`0x7CA4fa4da03c443d188e1E8D35ec1aDfA5090Ec6`](https://sepolia.etherscan.io/address/0x7CA4fa4da03c443d188e1E8D35ec1aDfA5090Ec6) |
| **Network** | Ethereum Sepolia (chain id 11155111) |
| **Compiler** | solc 0.8.24, optimizer on, 200 runs |
| **Source verified** | ✅ Etherscan ([view source](https://sepolia.etherscan.io/address/0x7CA4fa4da03c443d188e1E8D35ec1aDfA5090Ec6#code)) |
| **Deploy tx** | [`0xeca5d5bd700461926d9048548bdddbeccbe007c03316c2af642577421f4b202f`](https://sepolia.etherscan.io/tx/0xeca5d5bd700461926d9048548bdddbeccbe007c03316c2af642577421f4b202f) |

## Roles

| Role | Address |
|---|---|
| `DEFAULT_ADMIN_ROLE` + `BACKEND_ROLE` + `VALIDATOR_ROLE` (deployer) | [`0xd58fE99B5329B3602D7d32E5F98bc62F9372Db75`](https://sepolia.etherscan.io/address/0xd58fE99B5329B3602D7d32E5F98bc62F9372Db75) |
| `VALIDATOR_ROLE` (second validator) | [`0xd560a896c16BfD3A70E34d47aC463bD85A77c209`](https://sepolia.etherscan.io/address/0xd560a896c16BfD3A70E34d47aC463bD85A77c209) |

Second-validator role granted in tx [`0x38e1fefe3542860d6527ff7eef13d65e9c6873b3cad97d3202ce6aa9d7f981cb`](https://sepolia.etherscan.io/tx/0x38e1fefe3542860d6527ff7eef13d65e9c6873b3cad97d3202ce6aa9d7f981cb).

## Scenario A — legitimate project (Amazonia pilot) on Sepolia

Full flow against the live contract. Every state transition is a real
on-chain transaction.

| Step | Tx | What happened |
|---|---|---|
| Submit project | [`0x3579ed99…084d25`](https://sepolia.etherscan.io/tx/0x3579ed99b97eb171be271541fbcf03edf047dea81327f979094a2f807d084d25) | 133 H3 cells reserved for the Amazonia polygon; state → `Pending` |
| Attestation #1 (deployer / validator1) | [`0x286ad665…b9ae`](https://sepolia.etherscan.io/tx/0x286ad66503d8cde437a219cc106b61deaf0d362333d42f68f71a370ec7feb9ae) | First validator signs off on dataset / model / result hash |
| Attestation #2 (validator2) | [`0xead056bc…a02`](https://sepolia.etherscan.io/tx/0xead056bc1314e1f17f2cf8f443224b73aa9f193af1442f1c198afac9a3f70a02) | Threshold met → state → `Verified` (442 ha, 79.81% confidence) |
| Issue claim | [`0xbae33948…fa99`](https://sepolia.etherscan.io/tx/0xbae3394895766c094cb7d7a60dffc51b578d8dab1d76cdc5096b2560b919fa99) | state → `Issued` |

**Final on-chain state:** `Issued`, verified area `442 ha`, confidence `79.81%`,
attestations `2 of 2`.

## Scenario B — renamed duplicate blocked at contract level

| Step | Tx | What happened |
|---|---|---|
| Submit duplicate | [`0x5062cd78…a45c`](https://sepolia.etherscan.io/tx/0x5062cd78c34b5e04971062d8d43b082be483d666216b87165feafa3e7278a45c) | Contract reverted with `CellAlreadyClaimed(0x898af6166b7ffff, 0x055e…2c1)` |

The revert selector is `0x5bfccfba` — matching `CellAlreadyClaimed(uint64,bytes32)` in the contract ABI. The revert data embeds the specific cell id `0x898af6166b7ffff` and the project-id hash that currently owns it (Scenario A's hash). This is the on-chain, name-independent duplicate block.

## Provenance hashes committed on-chain (from Scenario A)

| Hash | Value |
|---|---|
| `datasetHash` | `0x2a263da5fb8de61d6ac15a6a993dd147ee4fc4ba858969ac8a034e6ff400ae9c` |
| `modelHash` | `0x997645dc6113af3e1ae1f44dc6607460fad7b2c811646328d0726a207dc3c549` |
| `resultHash` | `0xd016fcd81e648b1f68bf29014f066197f50571a0df57d8b13c9db143213f62c0` |

Any third party can rerun `pipeline/satellite.verify_from_fixture("amazonia-pilot-01", ...)` with the same polygon and recover these three hashes bit-for-bit.

## Reproducing this deployment

The exact commands used:

```bash
# Deploy (forge create — forge-script's gas estimation misbehaved on Sepolia
# during this window; use forge create directly)
cd contracts
source .env
forge create src/VeriCarbon.sol:VeriCarbon \
  --rpc-url "$SEPOLIA_RPC_URL" \
  --private-key "$PRIVATE_KEY" \
  --broadcast --verify \
  --etherscan-api-key "$ETHERSCAN_API_KEY"

# Grant validator2 role + fund it (300k gas on Sepolia right now, since the
# chain is in an inflated-estimate state — see note below)
# Then:
cd ..
RPC_URL="$SEPOLIA_RPC_URL" \
CONTRACT_ADDRESS=0x7CA4fa4da03c443d188e1E8D35ec1aDfA5090Ec6 \
BACKEND_PRIVATE_KEY="$PRIVATE_KEY" \
VALIDATOR2_PRIVATE_KEY="$VALIDATOR2_PRIVATE_KEY" \
CHAIN_ID=11155111 \
python scripts/run_scenarios.py
```

## Note on Sepolia gas during this run

While deploying, Sepolia was reporting an inflated `eth_estimateGas` for every
operation — ~200,000 gas for a simple ETH transfer (should be 21,000) and
~11.5 M gas for the contract deploy itself (would be ~1.5 M on mainnet with
normal estimates). Block gas limit was ~199 M. The chain executed everything
correctly; only the estimates were off. The code in `scripts/run_scenarios.py`
and `backend/chain.py` therefore uses generous explicit gas limits so the
transactions land regardless of the estimator's state.

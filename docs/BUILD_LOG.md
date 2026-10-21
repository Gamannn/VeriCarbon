# Build Log

Chronological record of what was built, what broke, and how it was fixed.
Written as we went, not post-hoc.

## 2026-10-15 to 2026-10-16

**Repo scaffolding.** Created `contracts/`, `pipeline/`, `backend/`,
`frontend/`, `docs/`, `scripts/`. Initialized Foundry with
`forge init --force`, installed OpenZeppelin v5.7.0.

**Smart contract.** Wrote `VeriCarbon.sol` with AccessControl roles,
state machine, cell-owner map, averaged attestation stats on finalization,
`ReentrancyGuard` on `issueClaim`.

Error encountered: `Copying nested calldata dynamic arrays to storage is
not implemented in the old code generator` when accepting
`string[] registryRefs` in `submitProject`. Fix: accept `bytes32
registryRefsHash` instead — more gas-efficient and matches the on-chain
vs off-chain split (store the hash, not the data).

Lint warnings for `uint64(x)` / `uint16(x)` down-casts in finalization.
Fix: explicit bounds-check and saturate before cast.

**Contract tests.** 22 tests including a 256-iteration fuzz
(`testFuzz_submitNeverCreatesOverlap`). First try had invalid hex
addresses (`0xV1`); fixed to `0xB01` style.

**Pipeline.** Wrote `geospatial.py`, `satellite.py` (fixture + live
modes), `entity_resolution.py`. 17 tests passing.

Missing `pyproj` from first install set — added, then everything green.

**Backend.** FastAPI with `/verify`, `/duplicate-check`, `/onchain/submit`,
`/onchain/attest`, `/onchain/project/<id>`, `/chain/status`, `/health`.
Pydantic schemas, `AccessControl` role-aware chain client. 6 API tests
passing including the negative "chain not configured → 503" case.

**End-to-end scenario script.** First run of `scripts/run_scenarios.py`:
Scenario A almost went through, but attestation #2 silently failed with
`status 0`. The script treated it as success and marched on to
`issueClaim`, which then reverted with `InvalidState` because only one
attestation had actually landed.

Fix: `ChainClient._send` now explicitly checks `receipt.status != 1` and
replays the tx with `eth_call` to recover the revert reason. Second run:
Scenario A passes all steps, Scenario B is blocked at the contract with
`CellAlreadyClaimed(0x898af6166b7ffff, 0x055e...2c1)`. Receipt saved to
`docs/demo_run.json`.

Also discovered that 133 cells × ~20k gas per `sstore` was bumping the
3M gas limit on fresh anvil restarts. Bumped the default gas to 6M.

**Frontend.** Chose a single-file React page over a full Next.js project
because of the 1-week budget. Dashboard loads React, Tailwind, Leaflet
from CDN, uses CSS tokens with light/dark variants, and calls the real
backend. Every button → real endpoint. "Chain not configured" is a
visible honest state.

**Docs.** `ARCHITECTURE.md`, `SECURITY_ASSESSMENT.md`,
`CLIMATE_IMPACT_ASSESSMENT.md`, `KNOWN_LIMITATIONS.md`,
`EVALUATION_REPORT.md`, `SELF_ASSESSMENT.md`, `DEMO_VIDEO.md`, this file.

**Still to do.** Sepolia deployment (depends on faucet), Slither pass,
record the demo video.

# Evaluation Report

This report lists what was measured, how, and on what data. Nothing here is
fabricated — numbers come from `forge test`, `pytest`, and the live demo run
captured in `docs/demo_run.json`.

## Smart contract

**Test suite:** `contracts/test/VeriCarbon.t.sol` — 22 tests covering
submission, attestation, flagging, issuance, rejection, access control,
duplicate detection at cell level, and a fuzz test for cell exclusivity.

**Last run (local anvil, Solidity 0.8.33 compiler):**

```
Ran 22 tests for test/VeriCarbon.t.sol:VeriCarbonTest
Suite result: ok. 22 passed; 0 failed; 0 skipped
```

Fuzz test `testFuzz_submitNeverCreatesOverlap` runs with **256 iterations**
and verifies that: for any pair of (start, count) ranges, the second
submission reverts iff the two ranges overlap, and otherwise both projects
end up as cell owners of their respective ranges.

**Gas (local, approximate):**

| Function | Gas (approx.) |
|---|---|
| submitProject (133 cells) | ~3.2M |
| attestVerification (first) | ~390k |
| attestVerification (second, triggers finalize) | ~254k |
| issueClaim | ~55k |
| flagProject | ~40k |

Submission is linear in cell count. For deployment on mainnet-priced chains
this is the dominant cost; for L2 / appchain it is negligible.

## Pipeline

**Test suite:** `pipeline/tests/` — 17 tests across
`test_geospatial.py`, `test_satellite.py`, and `test_entity_resolution.py`.

**Last run:**
```
17 passed in 1.61s
```

**What is checked:**

- `polygon_to_h3_cells` produces non-empty cells, all fitting in `uint64`.
- Polygon area in hectares is within ±20% of the Web-Mercator estimate for a
  known test geometry (acceptable for the latitudes we target; a production
  deployment should use an equal-area projection).
- Half-overlapping polygons are detected with `0.3 < cell_overlap_ratio < 0.8`.
- Non-overlapping polygons have `cell_overlap_count == 0` and
  `polygon_iou == 0`.
- Fixture verification outcomes match the labels in the fixture files:
  the Amazonia fixture `VERIFIES`, the Kalimantan fixture `REQUIRES_REVIEW`,
  and the Congo fixture `REJECTS` an inflated claim.
- Dataset / model / result hashes are deterministic for identical inputs
  and change when the polygon changes.
- Entity resolution finds duplicates with renamed names but overlapping
  geometry (classified MEDIUM or HIGH).
- Blocking by 50 km radius actually blocks far polygons from being compared.

## Backend API

**Test suite:** `backend/tests/test_api.py` — 6 tests.

```
6 passed in 10.16s
```

Covers `/health`, `/chain/status`, `/verify`, `/duplicate-check`, and the
negative case that `/onchain/submit` returns **503** when no chain is
configured — not a fake 200.

## End-to-end demo

**Script:** `scripts/run_scenarios.py` — runs a full submit → verify → attest
→ issue flow against a live chain.

**Scenario A (Amazonia pilot)** — captured in `docs/demo_run.json`:
```
state=Issued, cells=133, verified_area_ha=442, confidence_bps=7981 (79.81%)
```

**Scenario B (renamed duplicate)** — captured in `docs/demo_run.json`:
```
on-chain revert: CellAlreadyClaimed(cell=0x898af6166b7ffff, owner=0x055e…2c1)
```

The revert selector `0x5bfccfba` matches `CellAlreadyClaimed(uint64,bytes32)`
in the contract ABI.

## What has NOT been evaluated yet

- No held-out labeled test set for the entity-resolution score. The
  blueprint's weighted formula is a starting hypothesis; we have evidence it
  behaves sensibly on hand-constructed cases but no precision/recall curve
  on a corpus of real labeled pairs.
- No comparison against a baseline such as name-only or polygon-only matching.
- No live Sentinel-2 run included in automated tests (would require network
  access and credentials).
- No Slither / Mythril output included in this build.

These are the next evaluation items to add once credentials and labeled data
are available.

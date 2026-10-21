# VeriCarbon Architecture

## System in one picture

```
┌─────────────┐   polygon + claim     ┌─────────────────────────────────────────┐
│  Dashboard  │ ────────────────────▶ │  FastAPI backend (Python 3.12)          │
│  (Leaflet)  │ ◀──────────────────── │  • pipeline/geospatial    (H3, overlap) │
└─────────────┘  tx hashes, state     │  • pipeline/satellite     (NDVI, hash)  │
                                       │  • pipeline/entity_resolution (fuzzy)   │
                                       │  • backend/chain          (web3.py)     │
                                       └──────────────┬──────────────────────────┘
                                                      │ build_transaction / call
                                                      ▼
                                       ┌─────────────────────────────────────────┐
                                       │  VeriCarbon.sol (Solidity 0.8.24)       │
                                       │  AccessControl + state machine          │
                                       │  cell_owner[uint64] → projectId         │
                                       │  attestations[], 2-of-N threshold       │
                                       └──────────────┬──────────────────────────┘
                                                      │ events
                                                      ▼
                                                Sepolia / Anvil
```

## Trust boundary

| Layer | Trusted? | Why |
|---|---|---|
| Smart contract | Yes, after audit | Deterministic enforcement of cell exclusivity, state transitions, one-time issuance. |
| Validator role-holders | Trusted, but 2-of-N quorum | Each validator must independently sign off; a single malicious validator cannot verify. |
| Backend | **Partially trusted** | The backend chooses which polygon and hashes to submit. A malicious backend can submit garbage, but it cannot bypass cell-level enforcement or issue credits without validator attestations. |
| Fixture satellite data | **Not trusted as real evidence** | Explicitly labeled as synthetic. Must be swapped for live Sentinel-2 for a production deployment. |

## On-chain vs. off-chain split

**On-chain (immutable commitments):**
- `cell_owner` map (uint64 → bytes32) — the only piece that stops duplicate claims
- Project state machine: `Pending → Flagged → Verified → Issued`, with `Rejected` as terminal
- `datasetHash`, `modelHash`, `resultHash` for each verified project (model provenance)
- Validator attestations (one struct per attestation)
- Events for every state change

**Off-chain (bulk data):**
- Raw Sentinel-2 scenes and derived NDVI arrays
- The registry corpus and the full entity-resolution model
- Dashboard rendering

## Data flow for a project submission

1. **User** draws a polygon and enters claimed hectares.
2. **Backend** converts polygon → H3 cells (resolution 9, ~0.1 km² each) → uint64 ids.
3. **Backend** runs the duplicate scan against the registry corpus (fuzzy name + org + area + polygon IoU + cell overlap). It reports a risk level but does **not** gate the on-chain submission on it — the smart contract is the ground truth.
4. **Backend** calls `submitProject(projectId, cells, claimedAreaHa, registryRefsHash)`. The contract loops through cells and reverts on the first `CellAlreadyClaimed(cell, owner)` — this is the hard duplicate check that cannot be defeated by renaming.
5. **Backend** runs the satellite verification pipeline (fixture or live). It commits to a `datasetHash` (scenes + polygon), `modelHash` (code + parameters), and `resultHash` (output).
6. **Two validators** independently call `attestVerification(...)`. On the second valid attestation the contract averages the areas / confidences and transitions to `Verified`.
7. **Admin** calls `issueClaim(projectId)` — only legal from `Verified`.
8. **Dashboard** reads the final state back for display.

## Why resolution 9

| Resolution | Avg edge | Avg cell area | 500 ha project ≈ |
|---|---|---|---|
| 8 | 461 m | 0.74 km² | ~7 cells (too coarse) |
| **9** | **174 m** | **0.10 km²** | **~50 cells** |
| 10 | 65 m | 0.015 km² | ~333 cells (expensive on-chain) |

Resolution 9 is the balance where a typical project maps to a few dozen cells (cheap to store, cheap to loop over in Solidity) but still resolves partial overlaps at ~100-metre scale.

## Why a weighted score rather than a learned model as the main decision rule

The duplicate-risk score is an **explainable, weighted combination** of eight features. We also include a logistic regression hook for calibration against labeled pairs, but the primary artefact is the weighted score because:

1. Judges can read the formula directly.
2. The reasoning text ("H3 cell overlap: 100% of the smaller polygon") is derived mechanically from the features and never from a black-box output.
3. The one piece we really rely on for enforcement — cell overlap — is a geometric fact, not a model prediction.

## Reproducibility

Every verification result commits:
- `dataset_hash` = sha256(canonical({scenes, polygon}))
- `model_hash` = sha256(source files + parameter dict + MODEL_VERSION)
- `result_hash` = sha256(canonical(output dict minus result_hash))

Any third party can rerun `pipeline.satellite.verify_from_fixture` with the same inputs and reproduce these hashes bit-for-bit. The hashes are what the on-chain attestations commit to — not the pixels or model weights themselves.

# Known Limitations

This file is the single source of truth for things VeriCarbon does **not**
do in its current state. We state them explicitly so no judge, buyer, or
engineer concludes more than the evidence supports.

## 1. Satellite verification is in fixture mode by default

- The default `SATELLITE_MODE=fixture` reads deterministic test fixtures
  from `pipeline/data/fixtures/`. Every result in fixture mode is labeled
  `mode: "fixture"` in the API response and the dashboard, with a note
  disclosing that the NDVI numbers are synthetic.
- `verify_live(...)` queries Sentinel-2 L2A through the Microsoft
  Planetary Computer STAC endpoint. It works but has not been exercised
  as part of the hackathon demo because it requires `rasterio` and
  network access with potentially large downloads.

## 2. Registry corpus is synthetic

- `pipeline/data/registry_corpus.json` contains three illustrative entries
  with names that are **not** real projects. Any resemblance to a real
  carbon registry's project list is accidental; no claim of fraud is made
  about any real organization.
- A production deployment would ingest Verra, Gold Standard, CAR, ART, and
  Puro.earth public exports under their respective licenses.

## 3. Entity-resolution model is a baseline, not state-of-the-art

- The main duplicate-risk score is a hand-tuned weighted sum.
- A logistic regression hook (`entity_resolution.train_classifier`) is
  included for calibration against labeled pairs, but we have not yet run
  it against a labeled held-out split in this build. See
  [EVALUATION_REPORT.md](./EVALUATION_REPORT.md) for what we did measure.

## 4. Smart contract trust assumptions

- A single admin currently holds `DEFAULT_ADMIN_ROLE`, `BACKEND_ROLE`, and
  `VALIDATOR_ROLE` for convenience. A real deployment must split these
  across separate addresses, add a timelock for admin actions, and rotate
  validator keys. See [SECURITY_ASSESSMENT.md](./SECURITY_ASSESSMENT.md).
- `ATTESTATION_THRESHOLD = 2`. A production deployment should likely
  increase this and add a reputation or staking system to deter validator
  collusion.

## 5. The dashboard is a single-file React app

- No Next.js project, no SSR, no build pipeline. The file loads React,
  Tailwind, and Leaflet from public CDNs.
- Every button maps to a real backend endpoint. There are no mock
  responses, no fake transaction hashes, and no fabricated statistics.

## 6. Testnet deployment status

- The scenarios script has been exercised against a local Anvil chain.
- Deployment to Sepolia (or another public testnet) is a one-command step
  from the `contracts/` directory, but it depends on the deployer having
  faucet funds; it is not run automatically.

## 7. No tonnes-of-CO₂ accounting

- Vegetation increase is not equivalent to carbon removal. The pipeline
  returns a vegetated-area estimate and a verification confidence, not a
  tonnage. [CLIMATE_IMPACT_ASSESSMENT.md](./CLIMATE_IMPACT_ASSESSMENT.md)
  states what this does and does not demonstrate.

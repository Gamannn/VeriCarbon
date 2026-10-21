# Self-Assessment

Harsh judge's view of VeriCarbon as of the last build.

## Strongest evidence per criterion

### Climate impact (30%)
- Scenario B demonstrates on-chain enforcement that fuzzy-matching cannot
  provide. A renamed project with 100% overlapping polygon is rejected by
  the contract with the exact overlapping cell id in the revert payload.
- Climate-impact doc states what VeriCarbon does and does not do, which
  is itself a scientific-integrity win.

### Blockchain (30%)
- Clean state machine: `None → Pending → (Flagged) → Verified → Issued`,
  with `Rejected` as terminal and cell release.
- 22 passing contract tests including a 256-iteration fuzz for the
  cell-exclusivity invariant.
- Deploy script with optional `EXTRA_VALIDATOR` env for multi-validator
  bootstrap.
- `attestVerification` averages area + confidence across validators,
  stores dataset / model / result hash at finalization — judges can see
  model provenance on-chain.

### Feasibility (10%)
- All three test suites pass (`forge test`, `pytest pipeline/tests`,
  `pytest backend/tests`).
- Dashboard + backend + contract integration proved against local anvil
  in a reproducible script.
- Setup commands tested from a fresh clone.

### Security (10%)
- OpenZeppelin AccessControl with distinct BACKEND/VALIDATOR/ADMIN roles.
- `ReentrancyGuard` on `issueClaim`.
- Backend treats a reverted tx (status 0) as a failure — not as a silent
  success (this bug was caught and fixed during Scenario B integration).
- Security doc is honest about T4 (validator collusion) and T8 (backend
  trust).

### UX (10%)
- Single-page dashboard loads quickly, works on phone width (16px side
  gutter, responsive grid), designed with CSS tokens for light/dark.
- Every button hits a real backend endpoint. "Chain not configured" is
  a visible, honest state, not a crash or a fake success.

### Scalability (10%)
- H3 resolution-9 chosen with explicit trade-off justified in docs.
- Clear on-chain vs off-chain split.
- Gas numbers reported in the evaluation report.

## Weakest points

1. **No testnet deployment yet.** Depends on faucet funds. One-command
   deploy exists and has been exercised against local anvil.
2. **No labeled evaluation of the entity-resolution score.** The weighted
   formula is defensible and matches the blueprint, but we do not have
   precision/recall numbers from a real labeled corpus. Called out
   explicitly in the evaluation report and known-limitations file.
3. **No Slither output included.** Scheduled for the polish pass.
4. **Single-file dashboard instead of a full Next.js app.** Trade-off made
   consciously for a 1-week sprint; dashboard still meets every required
   screen in the brief (dashboard, submission form, verification results,
   evidence map, cross-registry comparison, duplicate-blocked screen,
   blockchain record).
5. **Satellite pipeline runs in fixture mode by default.** Live mode is
   implemented and runnable with network + rasterio.

## Next-highest-value actions (in order)

1. Deploy to Sepolia and record the address + explorer URL.
2. Run Slither and paste the full report in `docs/SECURITY_ASSESSMENT.md`.
3. Record the demo video (outline in `docs/DEMO_VIDEO.md`).
4. (Stretch) Add a labeled corpus of ~50 synthetic project pairs and
   produce precision/recall for the risk score.

# VeriCarbon Security Assessment

This document records the threat model, the invariants the smart contract enforces, the test evidence that proves those invariants, and the limitations we are **not** fixing in this hackathon prototype.

## Threats considered

| # | Threat | Mitigation | Residual risk |
|---|---|---|---|
| T1 | Duplicate claim submitted under a different name | On-chain `cell_owner` map reverts on `CellAlreadyClaimed(cell, owner)`. Enforced regardless of name or project id. | Low — demonstrated end-to-end in Scenario B. |
| T2 | Credits issued without verification | `issueClaim` only accepts projects in `Verified` state. `Verified` only reachable via two independent `attestVerification` calls. | Low — tested. |
| T3 | Credits issued twice for the same project | State transitions out of `Verified` on `issueClaim`, so a second call reverts with `InvalidState`. | Low — tested. |
| T4 | Malicious validator forces verification unilaterally | Threshold is 2 (configurable). Single attestation leaves state as `Pending`. | Medium — a quorum of malicious validators can forge any verification. Mitigation requires reputation / staking, out of scope. |
| T5 | Dataset / imagery swapped after attestation | `datasetHash`, `modelHash`, `resultHash` are stored per attestation. A different dataset produces a different hash and attestations will disagree. | Low — enforced by canonical JSON hashing. |
| T6 | Unauthorized account calls restricted functions | OpenZeppelin `AccessControl`: `BACKEND_ROLE`, `VALIDATOR_ROLE`, `DEFAULT_ADMIN_ROLE`. | Low — tested. |
| T7 | Projection manipulation (shift polygon to dodge overlap) | H3 cells are a global discrete grid. Shifting by less than a cell diameter still yields overlap; shifting beyond puts you in a different physical place. | Medium — a sub-cell shift combined with a cell-boundary alignment could evade detection at the margins. Higher resolution would reduce this. |
| T8 | Centralized backend compromise | A compromised backend can submit valid-looking projects but still cannot forge validator signatures or bypass `cell_owner`. | **High — acknowledged.** The backend is a single trusted service in this prototype; see [KNOWN_LIMITATIONS.md](./KNOWN_LIMITATIONS.md). |
| T9 | Reentrancy on state-changing functions | `issueClaim` is `nonReentrant`. All other state transitions are internal and do not call untrusted code. | Low. |

## Invariants proven by tests

All of these are enforced by `contracts/test/VeriCarbon.t.sol` (22 tests, all passing including a 256-run fuzz test):

| Invariant | Test |
|---|---|
| No two active projects own the same cell | `test_submitProject_revertsOnDuplicateCell`, `testFuzz_submitNeverCreatesOverlap` |
| Submission requires BACKEND_ROLE | `test_submitProject_revertsOnUnauthorized` |
| Attestation requires VALIDATOR_ROLE | `test_attestation_revertsOnUnauthorized` |
| A validator cannot attest twice | `test_attestation_revertsOnDoubleAttestation` |
| Confidence capped at 100% | `test_attestation_revertsOnOutOfRangeConfidence` |
| Issuance requires `Verified` state | `test_issueClaim_revertsIfNotVerified` |
| Issuance cannot repeat for the same project | `test_issueClaim_revertsOnDoubleIssuance` |
| Issued projects cannot be rejected | `test_reject_cannotRejectIssuedProject` |
| Rejected projects release their cells | `test_reject_releasesCellsForReuse`, `test_resolveFlag_rejectReleasesCells` |
| Confidence/area are averaged, not max/min | `test_attestation_advancesToVerifiedAtThreshold` |

Run them:

```bash
cd contracts
forge test -vvv
```

## Slither static analysis

Ran `slither src/VeriCarbon.sol` (slither-analyzer 0.11.6, solc 0.8.24). Full
output is in [`slither_report.txt`](./slither_report.txt). Summary of what it
found and our dispositions:

| Finding | File | Our take |
|---|---|---|
| `incorrect-equality`: `state == State.None` in `getRegistryRefsHash` | our code | **False positive.** Slither warns about strict equality in the context of block timestamps / token balances; comparing a `State` enum to `State.None` is the correct existence check and the only way to express "project not found". |
| `timestamp`: `attestationCount >= ATTESTATION_THRESHOLD` | our code | **False positive.** `attestationCount` is a `uint8` tally, not a timestamp. The comparison is intentional. |
| `timestamp`: `state == State.None` | our code | Same as the first finding (Slither reports it twice under two detectors). |
| `assembly` in `StorageSlot.sol` | OpenZeppelin v5.7.0 | Library noise — standard OZ helper, out of our scope. |
| `pragma`: mixed `^0.8.20` / `^0.8.24` / `>=0.4.16` | OpenZeppelin v5.7.0 | Library noise — OZ's pragma ranges, not controllable from our code. |
| `solc-version`: `^0.8.20` has known bugs | OpenZeppelin v5.7.0 | We compile with 0.8.24, which is outside the flagged bug set. Library noise. |

**Zero findings** in our source after excluding false positives on enum
comparisons. The static-analysis output is committed verbatim so a judge or
reviewer can confirm this independently.

## Other open items

1. **Formal invariant tests** — Foundry supports `invariant_*` test functions with randomised handler calls. The current fuzz test covers cell exclusivity for a pair of submissions; a handler-based invariant suite would cover arbitrarily long sequences.
2. **Deployment governance** — the deployer currently holds `DEFAULT_ADMIN_ROLE`, `BACKEND_ROLE`, and `VALIDATOR_ROLE` as a convenience for the demo. A real deployment should split these roles across separate addresses and use a timelock for admin actions.
3. **Validator rotation / staking** — out of scope for this hackathon; see T4.

## What the Slither pass does NOT prove

A clean static-analysis pass says the code does not contain known patterns of bugs. It does **not** prove the overall system is secure, because:

- The hardest security property here is **what the backend decides to submit** — static analysis of Solidity does not reach that.
- The economic model of a validator quorum requires reputation / staking to be meaningful; the contract alone cannot defend against a collusion of all validators.

We state this explicitly so no one reading the clean Slither output above concludes "VeriCarbon is secure" without also understanding T4 and T8.

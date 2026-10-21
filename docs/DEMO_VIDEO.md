# Demo Video Outline

Target runtime: 3 minutes. Record at 1080p, voice-over.

## Shot list

**00:00 — 00:15. The problem.**
> "A single ton of CO₂ cannot be sold twice, yet the voluntary carbon market
> keeps registering overlapping forest projects across different registries.
> VeriCarbon makes that impossible — not by a scoring heuristic, but by a
> smart contract."

Show the dashboard header + one sentence.

**00:15 — 00:50. Scenario A: a legitimate project goes through.**

Click **Scenario A** → **Run full pipeline**. On screen:
- Verification completes with 79.81% confidence over 442 ha.
- Duplicate scan returns MEDIUM (polygon overlaps the one entry we have).
- On-chain submit succeeds, 133 cells claimed.
- Attestations post, project ends in **Issued** state with real tx hashes.

Narrate the three provenance hashes (dataset / model / result) and point at
them in the UI.

**00:50 — 01:35. Scenario B: the renamed duplicate.**

Click **Scenario B**. Walk through:
- Different name, different organization, slightly smaller polygon.
- The off-chain duplicate scan flags it MEDIUM — 100% cell overlap, name
  similarity near zero.
- Press **Run full pipeline**. Submit fails.
- Zoom into the **"BLOCKED BY CONTRACT"** screen. Point at the
  `CellAlreadyClaimed(cell, owner)` revert data.

> "Even though the project is renamed, re-organized, and smaller, the
> contract refuses to assign the first already-claimed cell. That is the
> on-chain guarantee."

**01:35 — 02:15. Under the hood.**

Switch to a terminal split-screen with:
```
forge test -vvv
```
Show the 22 tests passing. Freeze on `testFuzz_submitNeverCreatesOverlap`.
Then switch to:
```
pytest pipeline/tests backend/tests -q
```
17 + 6 = 23 tests pass.

Mention the three provenance hashes, point at `pipeline/satellite.py`
(fixture labeling, canonical JSON hashing).

**02:15 — 02:45. Honest limitations.**

Over the dashboard footer:
> "VeriCarbon doesn't quantify tonnes of CO₂, doesn't prove additionality,
> and doesn't replace a registry. It is integrity infrastructure for the
> two failures a buyer actually feels: duplicates and unreproducible MRV."

Flash `docs/KNOWN_LIMITATIONS.md` in the editor for a beat.

**02:45 — 03:00. Call to action.**

> "Code at github.com/<your-handle>/VeriCarbon. Deployed on Sepolia at
> <address>. Thanks."

## Recording notes

- Use a dark macOS appearance to show the dashboard's dark-theme tokens.
- Keep the terminal font size large (18pt+); the on-screen text is the
  message.
- Do NOT edit the on-chain tx hashes or dashboard numbers. Every value
  comes from a real run. If a run fails during recording, retake rather
  than paste.

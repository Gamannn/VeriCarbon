# Demo Video Script

Target runtime: **3–5 minutes**. Record at 1080p with voice-over.

---

## Pre-recording checklist

1. Backend running: `cd backend && uvicorn app:app --port 8000`
2. Frontend running: `cd frontend && npm run dev` → open http://localhost:5174
3. Switch to **dark mode** (click the moon icon in the header) — reads better on video
4. Clear submission history (trash icon) so it starts empty
5. Bump terminal font to 18pt+ if showing terminal

---

## Shot list

### 00:00 – 00:20 · The problem

Show the full dashboard — header reads:
> **VeriCarbon** — Satellite-verified carbon credits with on-chain duplicate prevention

Voice-over:
> "Voluntary carbon markets have a trust problem: the same forest can be
> registered as a carbon offset on multiple registries. VeriCarbon solves this
> with satellite verification and an Ethereum smart contract that makes
> double-claiming physically impossible."

Point at the header badge "Sepolia connected" → this is a live blockchain.

---

### 00:20 – 01:15 · Scenario 1: Clean pass (East Africa)

1. Click **Examples** tab → **Fresh land in East Africa**
2. Form auto-fills. Point out: project ID, name, area.
3. Click **Submit for verification**
4. Walk through each pipeline step as it completes:
   - **Satellite verification**: VERIFIED badge, confidence %, NDVI stats
   - **Duplicate check**: LOW risk — no overlapping registry entries
   - **On-chain submit**: cells claimed, tx hash appears
   - **Attestation**: auto-posted, tx hash
   - **State**: Pending (1 of 2 attestations)
5. Scroll to **Analytics Dashboard** — point out:
   - Outcome donut + confidence gauge
   - NDVI vegetation bar chart
   - Area comparison (claimed vs vegetated)
   - Risk distribution pie — all green
   - "No significant overlap" in similarity panel
   - Gas & cell metrics
6. Note the entry in **Recent Submissions** with green badges

> "A legitimate project sails through — satellite confirms vegetation,
> no duplicates found, and the contract accepts the claim."

---

### 01:15 – 02:15 · Scenario 2: Duplicate rejection (Amazonia overlap)

1. Click **New submission** (top right)
2. Click **Examples** tab → **Overlapping with Amazonia registry**
3. Click **Submit for verification**
4. Walk through:
   - **Satellite verification**: VERIFIED — the land itself is fine
   - **Duplicate check**: HIGH risk — overlaps existing Amazonia entry
   - **On-chain submit**: **REJECTED — Duplicate land claim**
5. Zoom into the rejection alert:
   - `CellAlreadyClaimed` revert selector
   - Conflicting H3 cell ID
   - Owning project hash
   - Off-chain corroboration from the duplicate scan
6. Scroll to dashboard — radar chart now shows similarity fingerprint
   (high spatial overlap, cell overlap)

> "Even though this is a new project with a different name, the smart
> contract refuses it because the H3 cells are already claimed. This is
> enforced on-chain — no registry cooperation needed."

---

### 02:15 – 02:50 · Scenario 3: Medium risk (Kalimantan)

1. Click **New submission**
2. Click **Examples** tab → **Near Kalimantan peat registry**
3. Click **Submit for verification**
4. Point out:
   - Duplicate check returns MEDIUM risk — nearby but not overlapping
   - On-chain submit **succeeds** — cells are different
   - Dashboard shows medium-risk amber in the pie chart

> "The system flags the proximity but doesn't block it — the cells
> don't overlap, so the contract allows it. Risk information is
> preserved for human review."

---

### 02:50 – 03:30 · Architecture & transparency

Show the **Recent Submissions** panel — all three runs visible with badges.

Toggle to **light mode** to show theming works.

Voice-over:
> "Under the hood: a FastAPI backend runs satellite analysis using
> synthetic NDVI data — in production this connects to Sentinel-2.
> Duplicate detection uses H3 hexagonal cells at resolution 7 for
> precise spatial comparison. The Solidity contract on Sepolia
> enforces uniqueness — two validators must attest before a credit
> is issued."

Point at the footer disclaimer:
> "We're transparent: satellite results are labeled synthetic, and
> registry entries are a demo corpus. VeriCarbon is integrity
> infrastructure, not a replacement for a full MRV pipeline."

---

### 03:30 – 03:50 · Wrap up

> "VeriCarbon — satellite-verified, blockchain-enforced carbon credit
> integrity. Built for IEEE ClimateChain 2026, Track 1.
> Code at github.com/your-handle/VeriCarbon. Thank you."

---

## Recording tips

- Click each example template deliberately — pause 1 second before clicking Submit
- Let each pipeline step complete before narrating it
- The pipeline log at the bottom shows real-time progress — good to have visible
- All tx hashes and values come from live Sepolia runs — don't edit them
- If a run fails during recording, click New submission and retake that scenario
- Total should land between 3–5 minutes; don't rush

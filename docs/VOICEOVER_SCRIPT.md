# VeriCarbon Demo — Voiceover Script

Video duration: 3 minutes 22 seconds. No cuts needed — this is a clean recording.

---

## 0:00 – 0:15 · Opening

> This is VeriCarbon — satellite-verified carbon credits with on-chain duplicate prevention. The dashboard connects live to Ethereum Sepolia. On the left, a map shows existing registry entries. On the right, a three-stage pipeline: satellite analysis, duplicate detection, and blockchain enforcement.

---

## 0:15 – 0:25 · Template Selection

> The form offers four input modes. Under Examples, three pre-built scenarios demonstrate different outcomes. I select "Fresh land in East Africa" — a clean four hundred hectare parcel near Nairobi with no nearby registry entries.

---

## 0:25 – 0:40 · East Africa — Pipeline Results

> The pipeline runs. Satellite verification returns VERIFIED at seventy-four percent confidence. Vegetated area: fourteen hundred twenty-seven hectares — well above the four hundred claimed. NDVI is zero point six six four, seventy-two percent forest-like. The duplicate check finds no matches within fifty kilometres. Risk level: LOW.

---

## 0:40 – 0:55 · East Africa — Blockchain Accepts

> The smart contract accepts the submission. One hundred seventy-two H3 hexagonal cells are claimed on-chain. Two independent validators attest the verification. On-chain state: Verified. Attestations: two of two. Every step is logged with real Sepolia transaction hashes.

---

## 0:55 – 1:10 · East Africa — Analytics Dashboard

> The analytics dashboard confirms the outcome. VERIFIED donut, seventy-four percent confidence gauge, full NDVI vegetation bars, risk distribution entirely green. Project Status: Verified, two of two attestations, fourteen hundred twenty-seven hectares verified on-chain.

---

## 1:10 – 1:25 · Switching to Amazonia

> Now the fraud test. I click New Submission and load "Overlapping with Amazonia registry." This polygon in the Amazon Basin deliberately overlaps an existing entry — VCS-DEMO-1001. Form fills: Amazon Basin Reforestation, GreenForest Partners, four hundred fifty hectares.

---

## 1:25 – 1:45 · Amazonia — Duplicate Detected and Rejected

> Satellite returns VERIFIED at sixty-nine percent. But the duplicate check tells a different story. HIGH risk — score zero point nine five. H3 cell overlap: one hundred percent. Polygon, name, organization — all one hundred percent matches. The blockchain decision: REJECTED. CellAlreadyClaimed. The contract identifies the exact conflicting cell and the project that owns it.

---

## 1:45 – 2:05 · Amazonia — Dashboard

> The submission history now shows two entries. East Africa: Verified, LOW, on-chain. Amazonia: Verified satellite, HIGH risk, rejected. The analytics are all red — the radar chart lights up across all six axes. This is the fraud VeriCarbon catches.

---

## 2:05 – 2:30 · Live Example — Drawing a Polygon

> For the third scenario, I draw a custom polygon live. I navigate to the Amazonia area and drop points on the map, creating a shape that partially overlaps the existing registry entry. About half the cells overlap, half are fresh.

---

## 2:30 – 2:50 · Filling the Form

> I enter a completely different identity. Project ID: g_001. Organization: xyz. Area: fifty hectares. Description: random live example. Different name, different org — but the land partially overlaps.

---

## 2:50 – 3:10 · The Key Insight

> Satellite returns VERIFIED at seventy-five percent. The duplicate check finds VCS-DEMO-1001 — sixty-two percent cell overlap, sixty-three percent polygon overlap. But the names don't match. Risk score: just zero point three two — LOW. A name-based registry would let this through. But the blockchain still rejects it. CellAlreadyClaimed. Even partial overlap triggers the on-chain guard.

---

## 3:10 – 3:22 · Close

> Three submissions, three outcomes. Fresh land: verified and accepted. Exact duplicate: caught and rejected. Partial overlap with a fake identity: still rejected — because H3 cells don't lie. VeriCarbon. Satellite verification, hexagonal indexing, and smart contract enforcement. Built for IEEE ClimateChain 2026.

---

## Notes for AI Voice Generation

- **Pace**: Moderate, professional. Slightly slower at 2:50–3:10 (the punchline).
- **Emphasis**: VERIFIED, REJECTED, LOW, HIGH, CellAlreadyClaimed, two of two
- **Numbers**: Read naturally ("seventy-four percent", "fourteen hundred twenty-seven hectares")
- **Pauses**: Brief pause before VERIFIED/REJECTED reveals
- **Total**: ~500 words at 150 wpm = ~3:20

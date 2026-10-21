# Climate Impact Assessment

## What VeriCarbon actually does for the climate

VeriCarbon is **not a carbon registry** and does not quantify tonnes of CO₂e.
It is an infrastructure layer that aims to reduce two specific failures in the
existing voluntary carbon market:

1. **Double-counting across registries.** The same land getting registered in
   two or more registries, or by two different organizations, is a well-known
   problem that erodes buyer trust in offsets. VeriCarbon's smart contract
   makes double-counting a type error at the cell level: once a cell is
   claimed by an active project, no other project can claim it, regardless of
   name or legal entity.
2. **Opaque MRV.** Buyers today cannot easily reproduce the environmental
   evidence a registry relied on. VeriCarbon commits the dataset, model, and
   result hashes to the chain, so a third party can rerun the pipeline and
   verify they recover the exact same hashes.

## What VeriCarbon does **not** prove

- It does **not** prove the project removes a specific tonnage of CO₂.
- It does **not** address additionality (would the forest have grown anyway?).
- It does **not** address permanence (is the forest still there in 30 years?).
- It does **not** address leakage (did deforestation shift next door?).

Vegetation increase ≠ carbon removal. We state this explicitly in the
dashboard and in `pipeline/satellite.py`.

## Why that is still a climate contribution

The voluntary carbon market is estimated at tens of millions of credits per
year, with the Guardian / SourceMaterial 2023 investigation finding that a
large fraction of rainforest credits from a major registry represented
over-estimated reductions. Even a modest improvement in catching
double-counting and in making MRV reproducible has a direct effect on real
tonnes of CO₂e claimed vs. real tonnes removed, by shrinking the pool of
inflated or duplicated credits.

Our contribution is **integrity infrastructure** rather than a credit issuer.
That maps directly to the hackathon's Track 1 ("Carbon Markets and Emissions
Transparency") problem statement.

## Measured contribution in the prototype

The demo includes two end-to-end scenarios run against a local chain:

- **Scenario A** registers a 500 ha pilot. 133 H3 cells are claimed on-chain.
  Two validator attestations commit to the same dataset/model/result hash.
  The claim is issued.
- **Scenario B** attempts to register a *renamed* 450 ha project whose
  polygon overlaps Scenario A by 100%. The off-chain duplicate scan rates it
  MEDIUM risk based on cell overlap alone (name differs); the smart contract
  reverts the submission with `CellAlreadyClaimed(cell, owner)` and refuses
  to assign any cell.

The second scenario is the core climate claim: in a world without
VeriCarbon, that duplicate would have been issued and sold alongside the
original. In VeriCarbon's model, the duplicate cannot even enter the
pipeline.

## Scale considerations

Resolution-9 H3 cells are ~0.1 km² each. A pessimistic 1 million ha of
forest-restoration projects per year is ~1 billion cells, which is well
within reach of a modern L2 or a dedicated appchain. For Ethereum mainnet
the cost would be prohibitive; a cheaper EVM chain (Base, Polygon, Celo
Mainnet) or an appchain is the realistic deployment target.

## What's in `docs/demo_run.json`

A JSON record of the Scenario A and Scenario B run against the local chain,
captured at build time. It is **not** evidence of a real-world project — the
polygons are synthetic, the registry corpus is synthetic, and the satellite
imagery is a labeled fixture.

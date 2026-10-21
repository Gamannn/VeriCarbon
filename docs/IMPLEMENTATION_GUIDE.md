# VeriCarbon — Complete Implementation Guide

> This document is the single source of truth for building VeriCarbon.
> Every file, every function signature, every data model is specified here.
> A developer (or AI model) should be able to implement each component
> by reading the relevant section without needing any other context.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Directory Layout](#2-directory-layout)
3. [Smart Contracts (Phase 1)](#3-smart-contracts-phase-1)
4. [AI / ML Pipeline (Phase 2)](#4-ai--ml-pipeline-phase-2)
5. [Backend API (Phase 3A)](#5-backend-api-phase-3a)
6. [Frontend Dashboard (Phase 3B)](#6-frontend-dashboard-phase-3b)
7. [End-to-End Scripts (Phase 3C)](#7-end-to-end-scripts-phase-3c)
8. [Documentation (Phase 4)](#8-documentation-phase-4)
9. [Configuration Files](#9-configuration-files)
10. [Data Files](#10-data-files)
11. [Testing Strategy](#11-testing-strategy)
12. [Deployment](#12-deployment)

---

## 1. Project Overview

**VeriCarbon** is a verification layer for carbon credits that:
1. Checks environmental claims using satellite data + AI
2. Prevents double counting across registries using entity resolution + blockchain cell claims

**The demo story (2 scenarios):**
- **Scenario A (Legitimate):** "Amazon Reforestation Project" — 500 ha, real satellite data shows restoration, no duplicate found → REGISTERED on-chain
- **Scenario B (Duplicate):** "Amazonia Green Initiative" — different name, overlapping land → entity resolution finds 96% match, H3 cells already claimed → BLOCKED on-chain

**Tech Stack:**
- Smart Contracts: Solidity 0.8.24+ / Foundry / OpenZeppelin
- Blockchain: Base Sepolia (L2 testnet) — fallback: Sepolia L1
- Backend: Python 3.12 / FastAPI / web3.py
- Pipeline: scikit-learn, rapidfuzz, rasterio, geopandas, h3, shapely
- Frontend: Single-page React (CDN) + Tailwind CSS + Leaflet
- Data: Sentinel-2 via Planetary Computer STAC, ESA WorldCover

---

## 2. Directory Layout

```
VeriCarbon/
├── contracts/                    # Foundry project
│   ├── foundry.toml              # Foundry config
│   ├── .env.example              # Template for secrets
│   ├── src/
│   │   └── VeriCarbon.sol        # Main contract
│   ├── test/
│   │   ├── VeriCarbon.t.sol      # Unit + fuzz tests
│   │   └── Invariant.t.sol       # Invariant tests
│   └── script/
│       └── Deploy.s.sol          # Deployment script
│
├── pipeline/                     # Python AI/ML pipeline
│   ├── __init__.py               # Package init
│   ├── satellite.py              # Sentinel-2 fetch, NDVI, change detection
│   ├── geospatial.py             # H3 cells, polygon ops, overlap
│   ├── entity_resolution.py      # Cross-registry matching
│   ├── risk_scoring.py           # Duplicate risk computation
│   ├── hashing.py                # SHA-256 for dataset/model/result
│   └── tests/
│       ├── __init__.py
│       ├── test_satellite.py
│       ├── test_geospatial.py
│       ├── test_entity_resolution.py
│       └── test_risk_scoring.py
│
├── backend/                      # FastAPI service
│   ├── __init__.py
│   ├── app.py                    # FastAPI application + endpoints
│   ├── chain.py                  # web3.py blockchain interaction
│   ├── models.py                 # Pydantic request/response models
│   ├── config.py                 # Environment config
│   └── tests/
│       ├── __init__.py
│       └── test_app.py
│
├── frontend/                     # Single-page dashboard
│   └── index.html                # React + Tailwind + Leaflet (CDN, no build)
│
├── scripts/                      # Automation
│   ├── run_scenarios.py          # End-to-end demo (Scenario A + B)
│   └── reproduce.py              # Reproducibility: re-derive result hash
│
├── data/                         # Pilot data
│   ├── pilot_sites.geojson       # 2 pilot polygons
│   └── registry_records.json     # Cross-registry records for matching
│
├── docs/                         # Documentation
│   ├── IMPLEMENTATION_GUIDE.md   # This file
│   ├── ARCHITECTURE.md           # System architecture + diagram
│   ├── SECURITY_ASSESSMENT.md    # Threat model + controls
│   ├── CLIMATE_IMPACT_ASSESSMENT.md
│   ├── EVALUATION_REPORT.md      # Entity resolution metrics
│   ├── DEPLOYMENT.md             # Testnet addresses + tx hashes
│   └── KNOWN_LIMITATIONS.md      # Honest limitations
│
├── requirements.txt              # Python dependencies
├── README.md                     # Project README
├── .gitignore
└── .gitmodules                   # Foundry lib submodules
```

---

## 3. Smart Contracts (Phase 1)

### 3.1 File: `contracts/src/VeriCarbon.sol`

**Purpose:** On-chain registry that stores project verification state, enforces H3 cell exclusivity (no double claiming of land), manages validator attestations, and controls credit issuance.

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
```

#### 3.1.1 Roles (bytes32 constants)

```solidity
bytes32 public constant SUBMITTER_ROLE = keccak256("SUBMITTER_ROLE");
bytes32 public constant VALIDATOR_ROLE = keccak256("VALIDATOR_ROLE");
bytes32 public constant ASSESSOR_ROLE  = keccak256("ASSESSOR_ROLE");
bytes32 public constant REVIEWER_ROLE  = keccak256("REVIEWER_ROLE");
```

- `DEFAULT_ADMIN_ROLE` — can grant/revoke all roles (deployer gets this)
- `SUBMITTER_ROLE` — can call `submitProject`
- `VALIDATOR_ROLE` — can call `attestVerification`
- `ASSESSOR_ROLE` — can call `flagProject`
- `REVIEWER_ROLE` — can call `resolveFlag`

#### 3.1.2 Enums

```solidity
enum ProjectStatus {
    None,       // 0 — does not exist
    Pending,    // 1 — submitted, awaiting verification
    Verified,   // 2 — validators attested, ready for issuance
    Flagged,    // 3 — assessor flagged for review
    Issued,     // 4 — credits issued (terminal, one-time)
    Rejected    // 5 — rejected, cells released (terminal)
}
```

#### 3.1.3 Structs

```solidity
struct Project {
    bytes32 projectId;          // Unique project identifier (keccak256 of external ID)
    address owner;              // Address that submitted the project
    uint256 claimedAreaHa;      // Claimed restoration area in hectares
    uint256 verifiedAreaHa;     // AI-verified area (set by validators)
    uint16  confidenceBps;      // Confidence score in basis points (0-10000 = 0-100%)
    bytes32 datasetHash;        // SHA-256 of satellite scene list
    bytes32 modelHash;          // SHA-256 of model code + version
    bytes32 resultHash;         // SHA-256 of verification output
    ProjectStatus status;
    uint64  submittedAt;        // block.timestamp of submission
    uint64  verifiedAt;         // block.timestamp when Verified
    uint256 issuedTonnes;       // Claimed tonnes (set at issuance, not AI-derived)
    uint8   attestationCount;   // How many validators have attested
    string  registryRef;        // External registry reference (e.g., "VERRA:VCS-1234")
}

struct Attestation {
    address validator;
    bytes32 resultHash;         // Must match across validators
    uint256 verifiedAreaHa;
    uint16  confidenceBps;
    uint64  timestamp;
}
```

#### 3.1.4 State Variables

```solidity
uint8 public constant ATTESTATION_THRESHOLD = 2;  // 2-of-3 validators required

// projectId => Project
mapping(bytes32 => Project) public projects;

// H3 cell (uint64) => active projectId (bytes32). Zero means unclaimed.
mapping(uint64 => bytes32) public cellClaims;

// projectId => list of H3 cells it owns
mapping(bytes32 => uint64[]) public projectCells;

// projectId => validator address => Attestation
mapping(bytes32 => mapping(address => Attestation)) public attestations;

// registryRef hash => projectId (prevents same registry ref submitted twice)
mapping(bytes32 => bytes32) public registryRefToProject;
```

#### 3.1.5 Events

```solidity
event ProjectSubmitted(
    bytes32 indexed projectId,
    address indexed owner,
    uint256 claimedAreaHa,
    uint256 cellCount,
    string registryRef
);

event VerificationAttested(
    bytes32 indexed projectId,
    address indexed validator,
    bytes32 resultHash,
    uint256 verifiedAreaHa,
    uint16 confidenceBps
);

event ProjectVerified(
    bytes32 indexed projectId,
    bytes32 datasetHash,
    bytes32 modelHash,
    bytes32 resultHash,
    uint256 verifiedAreaHa,
    uint16 confidenceBps
);

event ProjectFlagged(
    bytes32 indexed projectId,
    address indexed assessor,
    uint16 riskBps,
    bytes32 evidenceHash
);

event ProjectRejected(bytes32 indexed projectId, uint256 cellsReleased);

event FlagResolved(bytes32 indexed projectId, bool approved);

event ClaimIssued(
    bytes32 indexed projectId,
    uint256 tonnes,
    uint64 timestamp
);
```

#### 3.1.6 Functions

**`submitProject`**

```solidity
/// @notice Submit a new project. Reserves H3 cells atomically.
/// @dev Reverts if ANY cell is already claimed or registryRef already used.
/// @param projectId   keccak256 of external project identifier
/// @param cells       Array of H3 resolution-9 cell indices (uint64)
/// @param claimedAreaHa  Claimed restoration area in hectares
/// @param registryRef    External registry reference string (e.g., "VERRA:VCS-1234")
function submitProject(
    bytes32 projectId,
    uint64[] calldata cells,
    uint256 claimedAreaHa,
    string calldata registryRef
) external onlyRole(SUBMITTER_ROLE)
```

**Behavior:**
1. Require `projectId` not already submitted (status == None)
2. Require `cells.length > 0`
3. If `registryRef` is not empty, hash it and require `registryRefToProject[hash] == bytes32(0)`
4. Loop through `cells`: require `cellClaims[cell] == bytes32(0)` for each
5. Loop through `cells`: set `cellClaims[cell] = projectId`
6. Store `projectCells[projectId] = cells`
7. Create the `Project` struct with status `Pending`, set `submittedAt = block.timestamp`
8. If registryRef not empty, set `registryRefToProject[hash] = projectId`
9. Emit `ProjectSubmitted`

**`attestVerification`**

```solidity
/// @notice Validator attests to verification results.
/// @dev At ATTESTATION_THRESHOLD matching attestations, project becomes Verified.
/// @param projectId     The project to attest
/// @param datasetHash   SHA-256 of satellite scene list used
/// @param modelHash     SHA-256 of model code + version
/// @param resultHash    SHA-256 of verification output
/// @param verifiedAreaHa  AI-estimated restoration area
/// @param confidenceBps   Confidence score (0-10000)
function attestVerification(
    bytes32 projectId,
    bytes32 datasetHash,
    bytes32 modelHash,
    bytes32 resultHash,
    uint256 verifiedAreaHa,
    uint16 confidenceBps
) external onlyRole(VALIDATOR_ROLE)
```

**Behavior:**
1. Require project status is `Pending` or `Flagged` (flagged projects can be re-attested after flag resolution)
2. Require this validator has not already attested for this project
3. Store the attestation in `attestations[projectId][msg.sender]`
4. Increment `project.attestationCount`
5. Emit `VerificationAttested`
6. If `attestationCount >= ATTESTATION_THRESHOLD`:
   - Count how many attestations share the same `resultHash` as this one
   - If count >= ATTESTATION_THRESHOLD: set status to `Verified`, store hashes, area, confidence, set `verifiedAt`
   - Emit `ProjectVerified`

**`flagProject`**

```solidity
/// @notice Flag a project for review (e.g., high duplicate risk).
/// @param projectId    The project to flag
/// @param riskBps      Risk score in basis points (0-10000)
/// @param evidenceHash Hash of the evidence/analysis supporting the flag
function flagProject(
    bytes32 projectId,
    uint16 riskBps,
    bytes32 evidenceHash
) external onlyRole(ASSESSOR_ROLE)
```

**Behavior:**
1. Require status is `Pending` or `Verified` (not already Issued, Rejected, or Flagged)
2. Set status to `Flagged`
3. Emit `ProjectFlagged`

**`resolveFlag`**

```solidity
/// @notice Resolve a flagged project.
/// @param projectId The flagged project
/// @param approve   true = return to Verified (if attestations met), false = Reject
function resolveFlag(
    bytes32 projectId,
    bool approve
) external onlyRole(REVIEWER_ROLE)
```

**Behavior:**
1. Require status is `Flagged`
2. If `approve == true`:
   - Require `attestationCount >= ATTESTATION_THRESHOLD`
   - Set status to `Verified`
   - Emit `FlagResolved(projectId, true)`
3. If `approve == false`:
   - Release all cells: loop through `projectCells[projectId]`, set `cellClaims[cell] = bytes32(0)`
   - Set status to `Rejected`
   - Emit `ProjectRejected` with cell count
   - Emit `FlagResolved(projectId, false)`

**`issueClaim`**

```solidity
/// @notice Issue carbon credits for a verified project. One-time only.
/// @param projectId The verified project
/// @param tonnes    Claimed tonnes of CO2e (project-reported, not AI-derived)
function issueClaim(
    bytes32 projectId,
    uint256 tonnes
) external onlyRole(SUBMITTER_ROLE)
```

**Behavior:**
1. Require status is `Verified`
2. Require `tonnes > 0`
3. Set `issuedTonnes = tonnes`
4. Set status to `Issued`
5. Emit `ClaimIssued`

**`rejectProject`**

```solidity
/// @notice Directly reject a pending project (admin/reviewer).
/// @param projectId The project to reject
function rejectProject(
    bytes32 projectId
) external onlyRole(REVIEWER_ROLE)
```

**Behavior:**
1. Require status is `Pending`
2. Release all cells (same as resolveFlag reject)
3. Set status to `Rejected`
4. Emit `ProjectRejected`

#### 3.1.7 View Functions

```solidity
/// @notice Get the full project struct
function getProject(bytes32 projectId) external view returns (Project memory);

/// @notice Get cells claimed by a project
function getProjectCells(bytes32 projectId) external view returns (uint64[] memory);

/// @notice Check which project owns a cell (bytes32(0) = unclaimed)
function getCellOwner(uint64 cell) external view returns (bytes32);

/// @notice Check if a specific validator has attested
function getAttestation(bytes32 projectId, address validator) external view returns (Attestation memory);

/// @notice Get project count (for dashboard)
function projectCount() external view returns (uint256);
```

Add a `uint256 public projectCount` that increments on each `submitProject`.

---

### 3.2 File: `contracts/test/VeriCarbon.t.sol`

**Purpose:** Unit and fuzz tests using Foundry's test framework.

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import "../src/VeriCarbon.sol";
```

**Test accounts setup:**
```solidity
address admin     = address(this);     // deployer = DEFAULT_ADMIN
address submitter = makeAddr("submitter");
address validator1 = makeAddr("validator1");
address validator2 = makeAddr("validator2");
address validator3 = makeAddr("validator3");
address assessor  = makeAddr("assessor");
address reviewer  = makeAddr("reviewer");
address attacker  = makeAddr("attacker");
```

**setUp():** Deploy contract, grant all roles.

**Tests to write (minimum 20):**

Submission:
1. `test_submitProject_success` — happy path, status becomes Pending, cells claimed
2. `test_submitProject_cellsReserved` — after submit, each cell maps to projectId
3. `test_submitProject_duplicateCell_reverts` — second project with overlapping cell reverts
4. `test_submitProject_duplicateProjectId_reverts` — same projectId reverts
5. `test_submitProject_duplicateRegistryRef_reverts` — same registryRef reverts
6. `test_submitProject_emptyCells_reverts` — zero cells reverts
7. `test_submitProject_unauthorized_reverts` — non-submitter reverts

Attestation:
8. `test_attestVerification_success` — one attestation stored
9. `test_attestVerification_reachesThreshold` — 2nd attestation with matching hash → status Verified
10. `test_attestVerification_mismatchHash` — 2 attestations with different hashes → not yet Verified
11. `test_attestVerification_doubleAttest_reverts` — same validator twice reverts
12. `test_attestVerification_wrongStatus_reverts` — attesting on Rejected project reverts

Flagging:
13. `test_flagProject_success` — status becomes Flagged
14. `test_flagProject_alreadyIssued_reverts` — can't flag after issuance

Flag resolution:
15. `test_resolveFlag_approve` — returns to Verified
16. `test_resolveFlag_reject_releasesCells` — cells become unclaimed, status Rejected
17. `test_resolveFlag_reject_cellsReclaimable` — after rejection, a new project can claim those cells

Issuance:
18. `test_issueClaim_success` — status becomes Issued, tonnes stored
19. `test_issueClaim_doubleIssue_reverts` — can't issue twice (status is already Issued)
20. `test_issueClaim_notVerified_reverts` — can't issue from Pending/Flagged

Fuzz tests:
21. `testFuzz_submitProject_noCellCollision(uint64[] cells1, uint64[] cells2)` — if two cell arrays overlap, second submission reverts; if they don't overlap, both succeed
22. `testFuzz_attestation_confidenceBounds(uint16 bps)` — confidence is stored correctly for any uint16 value

---

### 3.3 File: `contracts/test/Invariant.t.sol`

**Purpose:** Foundry invariant tests that hold across all random call sequences.

**Invariants to test:**

```solidity
/// INVARIANT 1: A cell never has two active owners.
/// For every cell in cellClaims, the owning project's status is not Rejected/None,
/// OR the cell is bytes32(0).
function invariant_cellExclusivity() public view {
    // Iterate tracked cells and verify each maps to exactly one active project
}

/// INVARIANT 2: Credits issued only from Verified, and only once.
/// If project.status == Issued, then issuedTonnes > 0 AND there exists a
/// prior state where status was Verified.

/// INVARIANT 3: Rejected projects have zero active cells.
/// If project.status == Rejected, all its cells in cellClaims must be bytes32(0).
```

Use a handler contract that calls `submitProject`, `attestVerification`, `flagProject`, `resolveFlag`, `issueClaim`, and `rejectProject` with random inputs. Track submitted cells in an array for the invariant check.

---

### 3.4 File: `contracts/script/Deploy.s.sol`

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Script.sol";
import "../src/VeriCarbon.sol";

contract Deploy is Script {
    function run() external {
        uint256 deployerKey = vm.envUint("PRIVATE_KEY");
        address extraValidator = vm.envOr("EXTRA_VALIDATOR", address(0));

        vm.startBroadcast(deployerKey);

        VeriCarbon vc = new VeriCarbon();
        // Deployer gets DEFAULT_ADMIN_ROLE automatically in constructor

        // Grant deployer all roles for demo convenience
        address deployer = vm.addr(deployerKey);
        vc.grantRole(vc.SUBMITTER_ROLE(), deployer);
        vc.grantRole(vc.VALIDATOR_ROLE(), deployer);
        vc.grantRole(vc.ASSESSOR_ROLE(), deployer);
        vc.grantRole(vc.REVIEWER_ROLE(), deployer);

        // Grant extra validator if provided (for 2-of-3 demo)
        if (extraValidator != address(0)) {
            vc.grantRole(vc.VALIDATOR_ROLE(), extraValidator);
        }

        vm.stopBroadcast();

        console.log("VeriCarbon deployed at:", address(vc));
    }
}
```

---

## 4. AI / ML Pipeline (Phase 2)

### 4.1 File: `pipeline/__init__.py`

```python
"""VeriCarbon AI/ML verification pipeline."""
```

### 4.2 File: `pipeline/satellite.py`

**Purpose:** Fetch Sentinel-2 imagery, compute NDVI, detect vegetation change, estimate restored area.

```python
"""Satellite verification pipeline using Sentinel-2 L2A via Planetary Computer."""

from dataclasses import dataclass
from typing import Optional
import numpy as np


@dataclass
class VerificationResult:
    """Output of the satellite verification pipeline."""
    claimed_area_ha: float          # From the project submission
    verified_area_ha: float         # AI-estimated restoration area
    confidence: float               # 0.0 to 1.0
    status: str                     # "VERIFIED", "REQUIRES_REVIEW", or "REJECTED"
    ndvi_baseline_mean: float       # Mean NDVI in baseline period
    ndvi_recent_mean: float         # Mean NDVI in recent period
    ndvi_change: float              # recent - baseline
    cloud_free_fraction: float      # Fraction of pixels not masked by cloud
    scene_ids_baseline: list[str]   # Sentinel-2 scene identifiers used
    scene_ids_recent: list[str]
    pixel_count_restored: int       # Pixels classified as restored
    pixel_count_total: int          # Total unmasked pixels in polygon


@dataclass
class SitePolygon:
    """A project's geographic boundary."""
    project_id: str
    name: str
    polygon: dict               # GeoJSON geometry (Polygon or MultiPolygon)
    claimed_area_ha: float
    country: str
    region: str


def fetch_sentinel2_scenes(
    polygon: dict,
    date_range: tuple[str, str],
    max_cloud_cover: int = 20,
) -> list[dict]:
    """
    Search Planetary Computer STAC for Sentinel-2 L2A scenes.

    Args:
        polygon: GeoJSON geometry dict
        date_range: ("2019-01-01", "2019-12-31") — start and end date
        max_cloud_cover: Maximum cloud cover percentage (0-100)

    Returns:
        List of STAC item dicts with 'id', 'datetime', 'assets' keys.
        Each asset has 'href' for the COG URL.

    Uses:
        pystac_client.Client.open("https://planetarycomputer.microsoft.com/api/stac/v1")
        planetary_computer.sign(item) to sign asset URLs

    Bands needed:
        B04 (Red), B08 (NIR) for NDVI
        SCL (Scene Classification Layer) for cloud masking
    """
    ...


def compute_ndvi(red: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """
    Compute NDVI = (NIR - Red) / (NIR + Red).
    Handle division by zero → return 0.0 for those pixels.

    Args:
        red: 2D array of Red band values (float)
        nir: 2D array of NIR band values (float)

    Returns:
        2D array of NDVI values, range [-1.0, 1.0]
    """
    ...


def cloud_mask_from_scl(scl: np.ndarray) -> np.ndarray:
    """
    Create a boolean mask from the Sentinel-2 SCL band.
    True = valid pixel, False = cloud/shadow/water.

    Valid SCL classes (keep these):
        4 = Vegetation
        5 = Bare soil
        6 = Water (exclude for forest)
        7 = Unclassified (keep cautiously)

    Masked classes (discard):
        0 = No data
        1 = Saturated/Defective
        2 = Dark area / shadow (cast shadows)
        3 = Cloud shadow
        8 = Cloud medium probability
        9 = Cloud high probability
        10 = Thin cirrus
        11 = Snow/Ice

    Returns:
        2D boolean array, same shape as scl
    """
    ...


def read_band_in_polygon(
    scene_asset_href: str,
    polygon: dict,
    band_name: str,
) -> tuple[np.ndarray, dict]:
    """
    Read a single band from a COG (Cloud Optimized GeoTIFF) clipped to a polygon.

    Uses rasterio.open() with the signed href.
    Uses rasterio.mask.mask(dataset, [polygon_shapely], crop=True).

    Args:
        scene_asset_href: Signed URL to the COG
        polygon: GeoJSON geometry dict
        band_name: For logging/debugging

    Returns:
        (band_array, transform_meta) — 2D numpy array + rasterio metadata
    """
    ...


def build_median_composite(
    scenes: list[dict],
    polygon: dict,
    bands: list[str],
) -> dict[str, np.ndarray]:
    """
    Build a per-pixel median composite from multiple scenes.
    This reduces cloud noise: for each pixel, take the median across dates.

    For each scene:
        1. Read B04 (Red), B08 (NIR), SCL
        2. Apply cloud mask from SCL
        3. Stack valid pixels

    Then compute per-pixel median across the stack.

    Args:
        scenes: List of STAC items (with signed assets)
        polygon: GeoJSON geometry
        bands: ["B04", "B08", "SCL"]

    Returns:
        {"red": 2D array, "nir": 2D array, "valid_mask": 2D boolean}
    """
    ...


def estimate_restoration(
    ndvi_baseline: np.ndarray,
    ndvi_recent: np.ndarray,
    valid_mask: np.ndarray,
    pixel_area_ha: float,
    ndvi_threshold: float = 0.15,
) -> tuple[float, int, int]:
    """
    Estimate restored area by counting pixels where NDVI increased significantly.

    A pixel is "restored" if:
        ndvi_recent - ndvi_baseline >= ndvi_threshold
        AND ndvi_recent >= 0.3 (minimum vegetation signal)
        AND valid_mask is True for that pixel in both periods

    Args:
        ndvi_baseline: 2D NDVI array for baseline period
        ndvi_recent: 2D NDVI array for recent period
        valid_mask: 2D boolean (True = valid in both periods)
        pixel_area_ha: Area of one pixel in hectares (for 10m Sentinel-2: ~0.01 ha)
        ndvi_threshold: Minimum NDVI increase to count as restoration

    Returns:
        (restored_area_ha, restored_pixel_count, total_valid_pixels)
    """
    ...


def compute_confidence(
    cloud_free_fraction: float,
    restored_share: float,
    scene_count_baseline: int,
    scene_count_recent: int,
) -> float:
    """
    Compute a confidence score (0.0 to 1.0) based on data quality indicators.

    Formula:
        base = 0.5
        + 0.2 * cloud_free_fraction          (more clear pixels = better)
        + 0.15 * min(scene_count / 5, 1.0)   (more scenes = better, cap at 5)
        + 0.15 * sigmoid(restored_share)      (extreme shares reduce confidence)

    Where scene_count = min(scene_count_baseline, scene_count_recent)
    And sigmoid maps 0.3-0.8 share to high confidence, extremes to lower.

    Returns:
        Confidence score clamped to [0.0, 1.0]
    """
    ...


def determine_status(share: float, confidence: float) -> str:
    """
    Decision rule for verification status.

    share = verified_area / claimed_area

    Rules:
        share >= 0.80 AND confidence >= 0.85 → "VERIFIED"
        share >= 0.50 AND confidence >= 0.50 → "REQUIRES_REVIEW"
        else → "REJECTED"
    """
    ...


def verify_project(site: SitePolygon, use_fixtures: bool = False) -> VerificationResult:
    """
    Full verification pipeline for one project.

    If use_fixtures=True, return a pre-computed VerificationResult
    (for testing and offline demo). The fixture data is defined in this function.

    Otherwise:
        1. fetch_sentinel2_scenes for baseline period (e.g., 2019-01-01 to 2019-12-31)
        2. fetch_sentinel2_scenes for recent period (e.g., 2023-01-01 to 2023-12-31)
        3. build_median_composite for each period
        4. compute_ndvi for each period
        5. estimate_restoration comparing the two
        6. compute_confidence
        7. determine_status
        8. Return VerificationResult with all fields populated

    The fixture mode should have:
        - Site "amazon-legit": verified_area=412, claimed=500, confidence=0.91, VERIFIED
        - Site "amazon-duplicate": same numbers (same land)
        - Site "stable-control": verified_area=5, claimed=500, confidence=0.88, REJECTED
    """
    ...
```

### 4.3 File: `pipeline/geospatial.py`

**Purpose:** Polygon to H3 cells, polygon overlap computation, area calculations.

```python
"""Geospatial operations: H3 cell conversion, overlap, area computation."""

import h3
import shapely.geometry
from shapely.ops import transform
import geopandas as gpd
import pyproj
from dataclasses import dataclass


@dataclass
class GeoAnalysis:
    """Result of geospatial analysis between two projects."""
    overlap_fraction: float     # 0.0 to 1.0 — fraction of new polygon overlapping existing
    centroid_distance_km: float # Distance between polygon centroids
    area_ratio: float           # min(area1, area2) / max(area1, area2)
    shared_cells: list[int]     # H3 cells in common (uint64 values)
    shared_cell_count: int


def polygon_to_h3_cells(
    geojson_geometry: dict,
    resolution: int = 9,
) -> list[int]:
    """
    Convert a GeoJSON polygon to a set of H3 cell indices.

    Uses h3.geo_to_cells() (or h3.polyfill_geojson in older API).

    At resolution 9:
        - Each cell ≈ 0.1 km² ≈ 10 ha
        - 500 ha ≈ 50 cells (manageable on-chain)

    Args:
        geojson_geometry: GeoJSON geometry dict (type: Polygon)
        resolution: H3 resolution (default 9)

    Returns:
        List of H3 cell indices as integers (uint64).
        Use h3.str_to_int() if h3 lib returns hex strings.
    """
    ...


def compute_polygon_area_ha(geojson_geometry: dict) -> float:
    """
    Compute the area of a GeoJSON polygon in hectares.

    Uses pyproj to transform from WGS84 to an equal-area projection,
    then shapely to compute area, then convert m² to hectares.

    Approach:
        1. Create shapely geometry from GeoJSON
        2. Use pyproj.Transformer for WGS84 → World Mollweide (ESRI:54009) or local UTM
        3. Transform geometry
        4. Return area / 10000 (m² to ha)
    """
    ...


def compute_overlap(
    polygon1: dict,
    polygon2: dict,
) -> float:
    """
    Compute the overlap fraction between two GeoJSON polygons.

    overlap_fraction = intersection_area / polygon1_area

    This is asymmetric: it answers "what fraction of polygon1 is covered by polygon2?"

    Returns:
        Float 0.0 to 1.0. Returns 0.0 if polygons don't intersect.
    """
    ...


def compute_centroid_distance_km(polygon1: dict, polygon2: dict) -> float:
    """
    Compute the distance between centroids of two polygons in kilometers.

    Uses pyproj.Geod(ellps="WGS84").inv() for geodesic distance.
    """
    ...


def analyze_geo_overlap(
    new_polygon: dict,
    existing_polygon: dict,
    resolution: int = 9,
) -> GeoAnalysis:
    """
    Full geospatial analysis between a new project and an existing one.

    1. Compute overlap fraction
    2. Compute centroid distance
    3. Compute area ratio
    4. Convert both to H3 cells, find shared cells

    Returns:
        GeoAnalysis with all fields populated
    """
    ...
```

### 4.4 File: `pipeline/entity_resolution.py`

**Purpose:** Determine if two project records from different registries refer to the same real-world project.

```python
"""Cross-registry entity resolution for carbon projects."""

from dataclasses import dataclass
from rapidfuzz import fuzz
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np


@dataclass
class RegistryRecord:
    """A project record from a carbon registry."""
    project_id: str         # Registry-specific ID (e.g., "VCS-1234")
    name: str               # Project name
    organization: str       # Developing organization
    country: str
    region: str             # State/province
    area_ha: float
    start_date: str         # ISO date
    description: str        # Project description text
    registry: str           # Which registry (e.g., "VERRA", "GOLD_STANDARD")
    polygon: dict | None    # GeoJSON geometry, if available


@dataclass
class MatchResult:
    """Result of comparing two registry records."""
    record_a: RegistryRecord
    record_b: RegistryRecord
    name_similarity: float          # 0-1, rapidfuzz token_sort_ratio / 100
    org_similarity: float           # 0-1
    description_similarity: float   # 0-1, TF-IDF cosine similarity
    area_ratio: float               # min/max of the two areas
    centroid_distance_km: float     # -1 if no polygons
    geo_overlap: float              # 0-1, -1 if no polygons
    country_match: bool
    region_match: bool
    entity_similarity: float        # Combined weighted score 0-1
    is_same_project: bool | None    # Ground truth label (None if unlabeled)


def compute_name_similarity(name1: str, name2: str) -> float:
    """
    Fuzzy string similarity between project names.

    Uses rapidfuzz.fuzz.token_sort_ratio (handles word reordering)
    and rapidfuzz.fuzz.partial_ratio (handles substrings).

    Return max(token_sort_ratio, partial_ratio) / 100.0

    Preprocessing: lowercase, strip "project", "initiative", "ltd", "inc",
    "programme", "program" — common noise words.
    """
    ...


def compute_org_similarity(org1: str, org2: str) -> float:
    """
    Fuzzy similarity between organization names.
    Same approach as name similarity.
    Preprocessing: strip "Ltd", "Inc", "LLC", "Foundation", "Corp".
    """
    ...


def compute_description_similarity(desc1: str, desc2: str) -> float:
    """
    TF-IDF cosine similarity between project descriptions.

    Fit TfidfVectorizer on [desc1, desc2], compute cosine similarity.
    Returns float 0.0 to 1.0.
    """
    ...


def compute_entity_similarity(match: MatchResult) -> float:
    """
    Weighted combination of all features into a single entity similarity score.

    Weights (tunable):
        name_similarity:        0.30
        org_similarity:         0.15
        description_similarity: 0.10
        area_ratio:             0.10
        geo_overlap:            0.25  (if available, else redistribute)
        country_match:          0.05  (1.0 if True, 0.0 if False)
        region_match:           0.05

    If geo_overlap is -1 (no polygons), redistribute its weight:
        name_similarity:        0.40
        org_similarity:         0.20
        description_similarity: 0.15
        area_ratio:             0.15
        country_match:          0.05
        region_match:           0.05

    Returns:
        Float 0.0 to 1.0
    """
    ...


def compare_records(a: RegistryRecord, b: RegistryRecord) -> MatchResult:
    """
    Compare two registry records and return a full MatchResult.

    1. Compute name_similarity
    2. Compute org_similarity
    3. Compute description_similarity
    4. Compute area_ratio = min(a.area_ha, b.area_ha) / max(...)
    5. If both have polygons: compute geo_overlap and centroid_distance
       Else: set both to -1.0
    6. Check country_match and region_match
    7. Compute entity_similarity
    8. Return MatchResult
    """
    ...


def find_matches(
    new_record: RegistryRecord,
    registry_db: list[RegistryRecord],
    threshold: float = 0.40,
    max_centroid_distance_km: float = 100.0,
) -> list[MatchResult]:
    """
    Find potential matches for a new record in the registry database.

    Blocking strategy (avoid N² comparisons):
        1. Filter to same country
        2. If polygons available, filter to centroid within max_centroid_distance_km
        3. Compare remaining with compare_records
        4. Return matches where entity_similarity >= threshold, sorted descending

    Returns:
        List of MatchResult, sorted by entity_similarity descending
    """
    ...
```

### 4.5 File: `pipeline/risk_scoring.py`

**Purpose:** Combine entity resolution and geospatial signals into a duplicate risk score.

```python
"""Duplicate risk scoring combining entity resolution and geospatial analysis."""

from dataclasses import dataclass
from enum import Enum


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass
class DuplicateRiskResult:
    """Output of the duplicate risk assessment."""
    risk_score: float           # 0.0 to 1.0
    risk_level: RiskLevel
    entity_similarity: float    # From entity resolution
    geo_overlap: float          # From geospatial analysis
    area_similarity: float      # min/max area ratio
    org_similarity: float       # Organization name similarity
    matched_project_id: str | None    # ID of the matched existing project
    matched_project_name: str | None
    matched_registry: str | None
    reason: str                 # Human-readable explanation


def compute_risk_score(
    entity_similarity: float,
    geo_overlap: float,
    area_similarity: float,
    org_similarity: float,
) -> float:
    """
    Compute duplicate risk score.

    Formula:
        risk = 0.35 * entity_similarity
             + 0.40 * geo_overlap
             + 0.10 * area_similarity
             + 0.15 * org_similarity

    All inputs are 0.0 to 1.0.
    Returns float 0.0 to 1.0.
    """
    ...


def classify_risk(risk_score: float) -> RiskLevel:
    """
    Classify risk score into a level.

    risk < 0.40  → LOW      (continue with registration)
    0.40 <= risk < 0.75 → MEDIUM  (flag for manual review)
    risk >= 0.75 → HIGH     (block automatic registration)
    """
    ...


def assess_duplicate_risk(
    entity_similarity: float,
    geo_overlap: float,
    area_similarity: float,
    org_similarity: float,
    matched_project_id: str | None = None,
    matched_project_name: str | None = None,
    matched_registry: str | None = None,
) -> DuplicateRiskResult:
    """
    Full duplicate risk assessment.

    1. compute_risk_score
    2. classify_risk
    3. Generate human-readable reason:
       - HIGH: "High duplicate risk: {score:.0%} match with {name} ({registry}).
               Geographic overlap: {geo:.0%}. Entity similarity: {entity:.0%}."
       - MEDIUM: "Moderate duplicate risk: ..."
       - LOW: "Low duplicate risk. No significant matches found."
    4. Return DuplicateRiskResult
    """
    ...
```

### 4.6 File: `pipeline/hashing.py`

**Purpose:** SHA-256 hashing for dataset provenance, model provenance, and result provenance.

```python
"""Reproducible hashing for on-chain provenance."""

import hashlib
import json


def hash_dataset(scene_ids: list[str]) -> str:
    """
    Hash the list of satellite scene IDs used for verification.
    This is the "dataset hash" committed on-chain.

    Process:
        1. Sort scene_ids alphabetically (deterministic ordering)
        2. Join with newline
        3. SHA-256 hash
        4. Return as "0x" + hex string (bytes32 compatible)
    """
    ...


def hash_model(model_version: str = "vericarbon-v1.0.0") -> str:
    """
    Hash the model/pipeline version.
    For MVP, this is a version string + the pipeline code commit hash.

    In a production system, this would hash the actual model weights file.

    Returns "0x" + hex string.
    """
    ...


def hash_result(verification_result: dict) -> str:
    """
    Hash the verification output for on-chain commitment.

    Process:
        1. Create a canonical dict with keys sorted:
           {
             "claimed_area_ha": ...,
             "confidence": round(x, 6),
             "status": ...,
             "verified_area_ha": round(x, 2),
           }
        2. json.dumps with sort_keys=True, no spaces
        3. SHA-256 hash
        4. Return as "0x" + hex string

    Rounding ensures deterministic hashing across different float representations.
    """
    ...


def verify_hash(data: str, expected_hash: str) -> bool:
    """
    Verify that SHA-256 of data matches the expected hash.
    Used by the reproducibility script.
    """
    ...
```

---

## 5. Backend API (Phase 3A)

### 5.1 File: `backend/config.py`

```python
"""Environment configuration."""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    RPC_URL: str = os.getenv("RPC_URL", "http://127.0.0.1:8545")
    CONTRACT_ADDRESS: str = os.getenv("CONTRACT_ADDRESS", "")
    BACKEND_PRIVATE_KEY: str = os.getenv("BACKEND_PRIVATE_KEY", "")
    VALIDATOR2_PRIVATE_KEY: str = os.getenv("VALIDATOR2_PRIVATE_KEY", "")
    CHAIN_ID: int = int(os.getenv("CHAIN_ID", "31337"))
    USE_FIXTURES: bool = os.getenv("USE_FIXTURES", "true").lower() == "true"

config = Config()
```

### 5.2 File: `backend/models.py`

**Purpose:** Pydantic models for API request/response schemas.

```python
"""Pydantic models for the VeriCarbon API."""

from pydantic import BaseModel, Field
from typing import Optional


# --- Request Models ---

class ProjectSubmission(BaseModel):
    """POST /projects/submit request body."""
    project_id: str = Field(..., example="FOREST-1042", description="Unique external project ID")
    name: str = Field(..., example="Amazon Reforestation Project")
    organization: str = Field(..., example="Green Earth Foundation")
    country: str = Field(..., example="Brazil")
    region: str = Field(..., example="Amazonas")
    claimed_area_ha: float = Field(..., gt=0, example=500.0)
    polygon: dict = Field(..., description="GeoJSON geometry (Polygon)")
    description: str = Field("", example="Forest restoration project in the Amazon basin")
    registry_ref: str = Field("", example="VERRA:VCS-1234")
    claimed_tonnes: float = Field(0, ge=0, example=45000.0)


# --- Response Models ---

class VerificationResponse(BaseModel):
    """Satellite verification results."""
    claimed_area_ha: float
    verified_area_ha: float
    confidence: float
    status: str                 # VERIFIED / REQUIRES_REVIEW / REJECTED
    ndvi_change: float
    scene_ids_baseline: list[str]
    scene_ids_recent: list[str]


class DuplicateCheckResponse(BaseModel):
    """Entity resolution and duplicate risk results."""
    risk_score: float
    risk_level: str             # LOW / MEDIUM / HIGH
    entity_similarity: float
    geo_overlap: float
    area_similarity: float
    org_similarity: float
    matched_project_id: Optional[str] = None
    matched_project_name: Optional[str] = None
    matched_registry: Optional[str] = None
    reason: str


class BlockchainRecord(BaseModel):
    """On-chain record details."""
    contract_address: str
    transaction_hash: str
    block_number: int
    project_id_bytes32: str     # The bytes32 on-chain
    status: str                 # Pending / Verified / Flagged / Issued / Rejected
    dataset_hash: str
    model_hash: str
    result_hash: str
    cell_count: int
    explorer_url: str           # Link to block explorer


class ProjectResponse(BaseModel):
    """Full project response combining all pipeline stages."""
    project_id: str
    name: str
    organization: str
    claimed_area_ha: float
    polygon: dict
    verification: VerificationResponse
    duplicate_check: DuplicateCheckResponse
    blockchain: Optional[BlockchainRecord] = None
    final_status: str           # APPROVED / FLAGGED / REJECTED
    h3_cells: list[str]         # Hex string representation of H3 cells


class DashboardStats(BaseModel):
    """Summary statistics for the dashboard."""
    total_projects: int
    projects_verified: int
    projects_flagged: int
    projects_rejected: int
    total_area_verified_ha: float
    duplicates_detected: int
```

### 5.3 File: `backend/chain.py`

**Purpose:** All blockchain interactions via web3.py.

```python
"""Blockchain interaction layer using web3.py."""

from web3 import Web3
from eth_account import Account
from typing import Optional
import json
import os


# Load the contract ABI from Foundry output
# After `forge build`, the ABI is at:
# contracts/out/VeriCarbon.sol/VeriCarbon.json -> ["abi"]
ABI_PATH = os.path.join(
    os.path.dirname(__file__), "..", "contracts", "out",
    "VeriCarbon.sol", "VeriCarbon.json"
)


class ChainClient:
    """Handles all smart contract interactions."""

    def __init__(self, rpc_url: str, contract_address: str, private_key: str, chain_id: int):
        """
        Initialize web3 connection and contract instance.

        Args:
            rpc_url: JSON-RPC endpoint (e.g., http://127.0.0.1:8545 or Alchemy URL)
            contract_address: Deployed VeriCarbon contract address
            private_key: Private key for signing transactions (backend's key)
            chain_id: Network chain ID (31337 for anvil, 84532 for Base Sepolia, 11155111 for Sepolia)
        """
        ...

    def _load_abi(self) -> list:
        """Load ABI from Foundry build output."""
        with open(ABI_PATH) as f:
            return json.load(f)["abi"]

    def _send_tx(self, fn, *args) -> dict:
        """
        Build, sign, and send a transaction. Wait for receipt.

        1. Build transaction with fn(*args).build_transaction({...})
        2. Sign with self.account.sign_transaction(tx)
        3. Send with self.w3.eth.send_raw_transaction(signed.raw_transaction)
        4. Wait for receipt with self.w3.eth.wait_for_transaction_receipt(tx_hash)
        5. Check receipt.status == 1, raise if 0

        Returns:
            Transaction receipt dict
        """
        ...

    def submit_project(
        self,
        project_id: str,
        cells: list[int],
        claimed_area_ha: int,
        registry_ref: str,
    ) -> dict:
        """
        Call submitProject on the contract.

        Args:
            project_id: String ID → keccak256 to bytes32
            cells: List of H3 cell indices as uint64
            claimed_area_ha: Area in hectares (uint256)
            registry_ref: External registry reference string

        Convert project_id to bytes32:
            Web3.keccak(text=project_id)

        Returns:
            Transaction receipt
        """
        ...

    def attest_verification(
        self,
        project_id: str,
        dataset_hash: str,
        model_hash: str,
        result_hash: str,
        verified_area_ha: int,
        confidence_bps: int,
        private_key: Optional[str] = None,
    ) -> dict:
        """
        Call attestVerification. Uses a different private key if provided
        (to simulate different validators).

        Hashes are passed as "0x..." hex strings → bytes32.
        confidence_bps: confidence * 10000 (e.g., 0.91 → 9100)
        """
        ...

    def flag_project(self, project_id: str, risk_bps: int, evidence_hash: str) -> dict:
        """Call flagProject."""
        ...

    def issue_claim(self, project_id: str, tonnes: int) -> dict:
        """Call issueClaim."""
        ...

    def get_project(self, project_id: str) -> dict:
        """
        Call getProject (view function, no gas).
        Returns decoded Project struct as a dict.

        Map the status integer to string:
            0=None, 1=Pending, 2=Verified, 3=Flagged, 4=Issued, 5=Rejected
        """
        ...

    def get_cell_owner(self, cell: int) -> str:
        """Call getCellOwner. Returns bytes32 as hex string."""
        ...

    def get_explorer_url(self, tx_hash: str) -> str:
        """
        Generate block explorer URL from tx hash.

        Base Sepolia: https://sepolia.basescan.org/tx/{tx_hash}
        Sepolia: https://sepolia.etherscan.io/tx/{tx_hash}
        Local: http://127.0.0.1:8545 (no explorer)
        """
        ...
```

### 5.4 File: `backend/app.py`

**Purpose:** FastAPI application with all endpoints.

```python
"""VeriCarbon Backend API."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from backend.config import config
from backend.models import (
    ProjectSubmission, ProjectResponse, DashboardStats,
    VerificationResponse, DuplicateCheckResponse, BlockchainRecord,
)
from backend.chain import ChainClient
from pipeline.satellite import SitePolygon, verify_project
from pipeline.geospatial import polygon_to_h3_cells
from pipeline.entity_resolution import RegistryRecord, find_matches, compare_records
from pipeline.risk_scoring import assess_duplicate_risk
from pipeline.hashing import hash_dataset, hash_model, hash_result

import json

# In-memory store for demo (no database needed for MVP)
projects_store: dict[str, ProjectResponse] = {}
registry_db: list[RegistryRecord] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load registry data on startup."""
    _load_registry_data()
    yield

app = FastAPI(
    title="VeriCarbon API",
    description="AI-powered MRV and cross-registry verification for carbon credits",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # For hackathon demo; restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)

chain: ChainClient | None = None

def get_chain() -> ChainClient:
    """Lazy-init the chain client."""
    global chain
    if chain is None:
        chain = ChainClient(
            rpc_url=config.RPC_URL,
            contract_address=config.CONTRACT_ADDRESS,
            private_key=config.BACKEND_PRIVATE_KEY,
            chain_id=config.CHAIN_ID,
        )
    return chain


def _load_registry_data():
    """Load registry records from data/registry_records.json into registry_db."""
    ...


# ─── ENDPOINTS ───────────────────────────────────────────────────

@app.post("/projects/submit", response_model=ProjectResponse)
async def submit_project(submission: ProjectSubmission):
    """
    Full pipeline: verify → match → risk score → blockchain submit.

    Steps:
        1. Run satellite verification (verify_project)
        2. Convert polygon to H3 cells
        3. Run entity resolution against registry_db
        4. Compute duplicate risk score
        5. Determine final action:
           - If verification REJECTED → don't submit to chain
           - If risk HIGH → submit to chain, then flag
           - If risk LOW/MEDIUM and verification VERIFIED → submit + attest + issue
        6. Submit to blockchain (submit_project)
        7. If verification passed:
           a. Compute hashes (dataset, model, result)
           b. Attest with validator 1 (backend key)
           c. Attest with validator 2 (second key) → triggers Verified status
           d. If risk LOW: issue claim
           e. If risk HIGH: flag project
        8. Store in projects_store
        9. Return ProjectResponse

    Error handling:
        - If chain submission reverts (e.g., cells already claimed),
          catch the error and return it as the "REJECTED" reason:
          "Blockchain rejection: cells already claimed by project {id}"
    """
    ...


@app.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str):
    """
    Get a project by ID from the in-memory store.
    Returns 404 if not found.
    """
    ...


@app.get("/projects", response_model=list[ProjectResponse])
async def list_projects():
    """Return all submitted projects, newest first."""
    ...


@app.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats():
    """
    Compute dashboard statistics from projects_store.
    Count projects by status, sum verified area, count duplicates detected.
    """
    ...


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "contract": config.CONTRACT_ADDRESS}
```

---

## 6. Frontend Dashboard (Phase 3B)

### 6.1 File: `frontend/index.html`

**Architecture:** Single HTML file using CDN-loaded React 18, Tailwind CSS, Leaflet, and ethers.js. No build step needed.

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VeriCarbon — Carbon Credit Verification</title>

    <!-- Tailwind CSS via CDN -->
    <script src="https://cdn.tailwindcss.com/3.4.1"></script>

    <!-- Leaflet CSS + JS -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css" />
    <script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>

    <!-- React 18 via CDN -->
    <script crossorigin src="https://cdnjs.cloudflare.com/ajax/libs/react/18.3.1/umd/react.production.min.js"></script>
    <script crossorigin src="https://cdnjs.cloudflare.com/ajax/libs/react-dom/18.3.1/umd/react-dom.production.min.js"></script>

    <!-- Babel standalone for JSX (acceptable for hackathon demo) -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/babel-standalone/7.24.7/babel.min.js"></script>

    <!-- ethers.js v6 -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/ethers/6.13.1/ethers.umd.min.js"></script>
</head>
```

#### 6.1.1 UI Components (React, in `<script type="text/babel">`)

**Component tree:**

```
<App>
  ├── <Navbar />                    # VeriCarbon logo, network indicator
  ├── <Dashboard />                 # Overview stats cards
  │   ├── <StatCard title="Projects Verified" />
  │   ├── <StatCard title="Area Verified" />
  │   ├── <StatCard title="Duplicates Detected" />
  │   └── <StatCard title="Projects Flagged" />
  ├── <SubmitProject />             # Submission form
  │   ├── Text inputs for name, org, area, etc.
  │   ├── Textarea for GeoJSON polygon paste
  │   └── Submit button → POST /projects/submit
  ├── <ProjectResult />             # After submission
  │   ├── <VerificationPanel />     # Satellite results + confidence
  │   │   ├── Claimed vs verified area bar
  │   │   ├── Confidence score with color
  │   │   └── Status badge (VERIFIED / REVIEW / REJECTED)
  │   ├── <DuplicatePanel />        # Entity resolution results
  │   │   ├── Risk level badge (LOW/MEDIUM/HIGH)
  │   │   ├── Match details (if found)
  │   │   └── Side-by-side comparison (if duplicate)
  │   ├── <MapView />               # Leaflet map
  │   │   ├── Polygon overlay (claimed boundary)
  │   │   ├── Overlapping polygon (if duplicate)
  │   │   └── H3 cell visualization (optional)
  │   └── <BlockchainPanel />       # On-chain record
  │       ├── Contract address
  │       ├── Transaction hash → link to explorer
  │       ├── Dataset/model/result hashes
  │       └── Status on-chain
  └── <DuplicateBlockedScreen />    # THE MONEY SHOT (shown when duplicate detected)
      ├── Red warning banner: "⚠ DUPLICATE DETECTED — Registration Blocked"
      ├── Side-by-side: New Project vs Existing Project
      │   ├── Name, org, registry, area for each
      │   ├── Same-project probability: 96.4%
      │   ├── Geographic overlap: 94%
      │   └── Risk level: HIGH
      ├── Map showing both overlapping polygons
      ├── "Credit registration has been blocked. Cells already claimed by project {id}."
      └── Blockchain rejection transaction link
```

#### 6.1.2 Key UI States

```
State 1: DASHBOARD (default)
    Show stats cards + list of past projects + submit form

State 2: SUBMITTING (loading)
    Show spinner + "Running verification pipeline..."
    Steps displayed:
    ✓ Fetching satellite data...
    ✓ Computing vegetation change...
    ✓ Running cross-registry matching...
    → Submitting to blockchain...

State 3: APPROVED (Scenario A result)
    Green banner: "✓ Project Verified and Registered"
    Verification panel, map, blockchain record

State 4: DUPLICATE BLOCKED (Scenario B result — the key screen)
    Red banner: "⚠ DUPLICATE DETECTED"
    Side-by-side comparison
    "Registration BLOCKED — cells already claimed"
    Map showing overlapping polygons in red
```

#### 6.1.3 API Integration

```javascript
const API_BASE = "http://localhost:8000";

// Submit a project
async function submitProject(formData) {
    const response = await fetch(`${API_BASE}/projects/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData),
    });
    if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || "Submission failed");
    }
    return response.json();
}

// Get dashboard stats
async function getDashboardStats() {
    const response = await fetch(`${API_BASE}/dashboard/stats`);
    return response.json();
}

// List all projects
async function listProjects() {
    const response = await fetch(`${API_BASE}/projects`);
    return response.json();
}
```

#### 6.1.4 Color Scheme

```css
/* Use Tailwind classes */
/* Status colors: */
/*   VERIFIED / APPROVED: bg-green-100 text-green-800 border-green-500 */
/*   REQUIRES_REVIEW / MEDIUM: bg-yellow-100 text-yellow-800 border-yellow-500 */
/*   REJECTED / HIGH / BLOCKED: bg-red-100 text-red-800 border-red-500 */
/*   PENDING / LOW: bg-blue-100 text-blue-800 border-blue-500 */

/* Map polygon colors: */
/*   Claimed polygon: blue (#3b82f6) */
/*   Verified area: green (#22c55e) */
/*   Overlapping/duplicate: red (#ef4444) */
/*   Existing project: orange (#f97316) */
```

#### 6.1.5 Leaflet Map Setup

```javascript
function MapView({ polygon, overlapPolygon, center }) {
    // Initialize Leaflet map
    // useEffect to create map on mount:
    //   L.map(container).setView(center, 10)
    //   L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png").addTo(map)
    //
    // Add claimed polygon:
    //   L.geoJSON(polygon, { style: { color: "#3b82f6", weight: 2, fillOpacity: 0.2 } })
    //
    // If overlapPolygon exists (duplicate case):
    //   L.geoJSON(overlapPolygon, { style: { color: "#ef4444", weight: 2, fillOpacity: 0.3 } })
    //
    // Fit bounds to polygon(s)
}
```

---

## 7. End-to-End Scripts (Phase 3C)

### 7.1 File: `scripts/run_scenarios.py`

**Purpose:** Run both demo scenarios end-to-end against a live chain (local or testnet).

```python
"""
Run VeriCarbon demo scenarios against a live chain.

Usage:
    # Against local anvil:
    RPC_URL=http://127.0.0.1:8545 \
    CONTRACT_ADDRESS=0x... \
    BACKEND_PRIVATE_KEY=0x... \
    VALIDATOR2_PRIVATE_KEY=0x... \
    CHAIN_ID=31337 \
    python scripts/run_scenarios.py

Scenario A (Legitimate project):
    1. Submit "Amazon Reforestation Project" with polygon A
    2. Run satellite verification → VERIFIED (412 ha / 500 ha, confidence 91%)
    3. Entity resolution → no match found
    4. Risk: LOW
    5. Submit to chain → cells claimed → attestations → Verified → Claim issued
    6. Print: ✓ Scenario A PASSED — project registered

Scenario B (Duplicate project):
    1. Submit "Amazonia Green Initiative" with polygon B (94% overlap with A)
    2. Run satellite verification → VERIFIED (similar results, same land)
    3. Entity resolution → 96% match with Scenario A project
    4. Risk: HIGH
    5. Submit to chain → REVERTS because cells already claimed
    6. Print: ✓ Scenario B PASSED — duplicate correctly blocked

Output:
    - Print step-by-step results to stdout
    - Save full output to docs/demo_run.json
"""
```

### 7.2 File: `scripts/reproduce.py`

**Purpose:** Reproducibility script that re-derives result hashes from raw inputs.

```python
"""
Reproducibility script: re-derive the result hash from raw inputs.

This proves that the on-chain hash matches what the pipeline produces.

Usage:
    python scripts/reproduce.py --project-id FOREST-1042

Steps:
    1. Load the pilot site polygon from data/pilot_sites.geojson
    2. Run the verification pipeline (same parameters)
    3. Compute dataset_hash, model_hash, result_hash
    4. Read the on-chain hashes (via web3 or from docs/demo_run.json)
    5. Compare and print MATCH / MISMATCH for each
"""
```

---

## 8. Documentation (Phase 4)

### 8.1 `docs/ARCHITECTURE.md`

**Contents:**
1. One-paragraph system overview
2. Architecture diagram (ASCII or embedded image):

```
┌──────────────┐    ┌──────────────────┐    ┌───────────────────┐
│   Frontend   │───▶│  Backend (API)   │───▶│  Smart Contract   │
│  React +     │    │  FastAPI +       │    │  VeriCarbon.sol   │
│  Leaflet     │    │  web3.py         │    │  Base Sepolia     │
└──────────────┘    └───────┬──────────┘    └───────────────────┘
                            │
                  ┌─────────┴─────────┐
                  │                   │
         ┌────────▼──────┐  ┌────────▼──────────┐
         │ AI Pipeline   │  │ Entity Resolution  │
         │ Sentinel-2    │  │ Cross-Registry     │
         │ NDVI + Change │  │ Matching + Risk    │
         └───────────────┘  └────────────────────┘
```

3. Data flow for each scenario (A and B)
4. On-chain vs off-chain data split table
5. Component responsibilities (AI decides, blockchain enforces)

### 8.2 `docs/SECURITY_ASSESSMENT.md`

**Contents (1-2 pages):**
1. Scope and assets (what we protect)
2. Trust assumptions (who is trusted for what)
3. Threat model table (9 threats from blueprint section 9, with defenses)
4. Controls implemented: AccessControl roles, cell exclusivity invariant, hashing, 2-of-3 attestation
5. Testing: forge test results (unit + fuzz + invariant), Slither results
6. Known limitations: centralized backend, public location data, AI error bounds, no additionality assessment
7. Roadmap: decentralized validators, ZK privacy, dispute mechanism

### 8.3 `docs/CLIMATE_IMPACT_ASSESSMENT.md`

**Contents (1-2 pages):**
1. Problem scale: cite analyses of carbon credit quality issues, double counting incidents
2. Measured results from our evaluation: duplicate pairs found, area at risk, tonnes at risk
3. Scenario projections: "If deployed across X% of voluntary market projects..."
4. Honest framing: protects credit integrity, does not directly remove emissions
5. Adoption path: pilot with registries, auditors, corporate buyers

### 8.4 `docs/EVALUATION_REPORT.md`

**Contents:**
1. Entity resolution evaluation: precision, recall, F1, confusion matrix
2. Methodology: train/test split, synthetic positive creation method
3. Limitations: synthetic positives are easier than real-world duplicates
4. Satellite verification accuracy: verified area vs ground truth (if available)
5. Risk scoring calibration: threshold sensitivity analysis

### 8.5 `docs/KNOWN_LIMITATIONS.md`

**Contents:**
1. AI verification covers area change only, not tonnes of CO2e
2. Additionality, permanence, and leakage are out of scope
3. Entity resolution tested on synthetic duplicates only
4. Backend is a single trusted party (centralization)
5. Location data is public (no ZK privacy)
6. Sentinel-2 resolution (10m) limits small-project detection
7. H3 resolution-9 cells (~10 ha) may be too coarse for small plots

### 8.6 `docs/DEPLOYMENT.md`

**Contents:**
- Network: Base Sepolia (or Sepolia)
- Contract address: `0x...`
- Deployment transaction: `0x...` → explorer link
- Etherscan verification status
- Scenario A transaction hashes
- Scenario B transaction hashes (revert evidence)
- Deployer address
- Faucet used

---

## 9. Configuration Files

### 9.1 `contracts/foundry.toml`

```toml
[profile.default]
src = "src"
out = "out"
libs = ["lib"]
solc_version = "0.8.24"
optimizer = true
optimizer_runs = 200
via_ir = false

[fuzz]
runs = 256
max_test_rejects = 65536

[invariant]
runs = 256
depth = 50
fail_on_revert = false

[rpc_endpoints]
sepolia = "${SEPOLIA_RPC_URL}"
base_sepolia = "${BASE_SEPOLIA_RPC_URL}"
local = "http://127.0.0.1:8545"

[etherscan]
sepolia = { key = "${ETHERSCAN_API_KEY}" }
base_sepolia = { key = "${BASESCAN_API_KEY}" }
```

### 9.2 `contracts/.env.example`

```env
# Deployer private key (NEVER commit the real .env)
PRIVATE_KEY=0x...

# RPC URLs (get free from Alchemy or QuickNode)
SEPOLIA_RPC_URL=https://eth-sepolia.g.alchemy.com/v2/YOUR_KEY
BASE_SEPOLIA_RPC_URL=https://base-sepolia.g.alchemy.com/v2/YOUR_KEY

# Block explorer API keys (for contract verification)
ETHERSCAN_API_KEY=YOUR_KEY
BASESCAN_API_KEY=YOUR_KEY

# Second validator address (for 2-of-3 attestation demo)
EXTRA_VALIDATOR=0x...
```

### 9.3 `requirements.txt`

```
# Core
fastapi==0.115.6
uvicorn[standard]==0.32.1
pydantic==2.10.4
python-dotenv==1.0.1

# Web3
web3==7.6.0
eth-account==0.13.4

# Geospatial
shapely==2.0.6
geopandas==1.0.1
h3==4.1.2
pyproj==3.7.0

# Satellite + raster
rasterio==1.4.3
pystac-client==0.8.5
planetary-computer==1.0.0

# ML + fuzzy
scikit-learn==1.5.2
rapidfuzz==3.10.1
numpy==2.1.3
pandas==2.2.3

# Dev
pytest==8.3.4
httpx==0.28.1
```

### 9.4 `.gitignore`

```gitignore
# Python
__pycache__/
*.py[cod]
.venv/
*.egg-info/
dist/

# Foundry
contracts/out/
contracts/cache/
contracts/broadcast/

# Environment (NEVER commit secrets)
.env
contracts/.env

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db

# Data (large files — keep GeoJSON, ignore rasters)
data/*.tif
data/*.tiff

# Node
node_modules/
```

---

## 10. Data Files

### 10.1 `data/pilot_sites.geojson`

**Contains 3 pilot sites as GeoJSON FeatureCollection:**

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {
        "project_id": "FOREST-1042",
        "name": "Amazon Reforestation Project",
        "organization": "Green Earth Foundation",
        "country": "Brazil",
        "region": "Amazonas",
        "claimed_area_ha": 500,
        "registry": "VERRA",
        "registry_ref": "VERRA:VCS-1042",
        "role": "legitimate"
      },
      "geometry": {
        "type": "Polygon",
        "coordinates": [[ /* ~500 ha polygon in Amazonas */ ]]
      }
    },
    {
      "type": "Feature",
      "properties": {
        "project_id": "GFR-18",
        "name": "Amazonia Green Initiative",
        "organization": "GreenForest Initiative Ltd",
        "country": "Brazil",
        "region": "Amazonas",
        "claimed_area_ha": 480,
        "registry": "GOLD_STANDARD",
        "registry_ref": "GS:GFR-18",
        "role": "duplicate_synthetic"
      },
      "geometry": {
        "type": "Polygon",
        "coordinates": [[ /* 94% overlap with FOREST-1042, slightly shifted */ ]]
      }
    },
    {
      "type": "Feature",
      "properties": {
        "project_id": "CONTROL-001",
        "name": "Stable Forest Control Site",
        "organization": "Test Organization",
        "country": "Brazil",
        "region": "Para",
        "claimed_area_ha": 500,
        "registry": "NONE",
        "registry_ref": "",
        "role": "negative_control"
      },
      "geometry": {
        "type": "Polygon",
        "coordinates": [[ /* stable forest area, no change */ ]]
      }
    }
  ]
}
```

**How to choose real coordinates:**
1. Go to Google Earth or geojson.io
2. Find a known reforestation area in Brazil (Amazonas state)
3. Draw a ~500 ha polygon (~2.2 km × 2.2 km square, or irregular shape)
4. For the duplicate: shift the polygon by ~100-200 meters (94% overlap)
5. For the control: pick a location 50+ km away with stable old-growth forest
6. Export as GeoJSON

### 10.2 `data/registry_records.json`

**Contains 30-50 records from "multiple registries" for entity resolution testing.**

```json
[
  {
    "project_id": "VCS-1042",
    "name": "Amazon Reforestation Project",
    "organization": "Green Earth Foundation",
    "country": "Brazil",
    "region": "Amazonas",
    "area_ha": 500,
    "start_date": "2020-03-15",
    "description": "Large-scale forest restoration in degraded Amazon basin areas...",
    "registry": "VERRA",
    "polygon": { "type": "Polygon", "coordinates": [[...]] }
  },
  {
    "project_id": "GS-GFR-18",
    "name": "Amazonia Green Initiative",
    "organization": "GreenForest Initiative Ltd",
    "country": "Brazil",
    "region": "Amazonas",
    "area_ha": 480,
    "start_date": "2020-04-01",
    "description": "Reforestation initiative in the Amazon region...",
    "registry": "GOLD_STANDARD",
    "polygon": { "type": "Polygon", "coordinates": [[...]] }
  }
  // ... 28-48 more records, mix of:
  //   - Real distinct projects (from public registry exports)
  //   - Synthetic duplicates (perturbed names, shifted polygons, rounded areas)
  //   - Different countries and registries for diversity
  //
  // Label each record with:
  //   "is_synthetic": true/false
  //   "duplicate_of": "VCS-1042" or null
]
```

**How to create realistic records:**
1. Download public project lists from Verra and Gold Standard
2. Pick 20-30 real projects across different countries
3. Create 10-15 synthetic duplicates by:
   - Abbreviating names ("Amazon Reforestation" → "Amaz. Reforest.")
   - Reordering words ("Forest Restoration Project" → "Project for Forest Restoration")
   - Changing org suffixes ("Ltd" → "Foundation" → "Initiative")
   - Shifting polygons by 50-200 meters
   - Rounding areas (500 → 480, 500 → 510)
   - Using different date formats or shifting dates by days
4. Mark all synthetics clearly with `is_synthetic: true`

---

## 11. Testing Strategy

### 11.1 Contract Tests

Run with: `cd contracts && forge test -vv`

- **Unit tests** (`VeriCarbon.t.sol`): 20+ tests covering all functions, roles, state transitions, and revert conditions
- **Fuzz tests** (in same file): Random cell arrays, confidence values
- **Invariant tests** (`Invariant.t.sol`): Cell exclusivity, issued-only-from-verified, rejected-releases-cells

### 11.2 Pipeline Tests

Run with: `pytest pipeline/tests -v`

All pipeline tests use **fixtures** (pre-computed values) so they run without network access.

**`test_satellite.py`:**
- `test_compute_ndvi` — known input arrays → expected NDVI values
- `test_cloud_mask` — SCL array → expected mask
- `test_determine_status` — various share/confidence combos → expected status
- `test_verify_project_fixture` — fixture mode returns expected VerificationResult

**`test_geospatial.py`:**
- `test_polygon_to_h3_cells` — known polygon → expected cell count range
- `test_compute_overlap_identical` — same polygon → 1.0
- `test_compute_overlap_disjoint` — non-overlapping → 0.0
- `test_compute_overlap_partial` — shifted polygon → ~0.9x
- `test_compute_area` — known polygon → expected area ±5%

**`test_entity_resolution.py`:**
- `test_identical_records` — same record → similarity ~1.0
- `test_completely_different` — unrelated → similarity < 0.3
- `test_perturbed_name` — "Amazon Reforestation Project" vs "Amaz. Reforest. Proj." → high similarity
- `test_same_org_different_name` — org match boosts score
- `test_geographic_overlap_boosts_score` — overlapping polygons increase entity similarity

**`test_risk_scoring.py`:**
- `test_low_risk` — all low signals → LOW
- `test_high_risk` — all high signals → HIGH
- `test_medium_risk` — mixed signals → MEDIUM
- `test_cell_overlap_overrides` — any shared cells → always HIGH regardless of score

### 11.3 Backend Tests

Run with: `pytest backend/tests -v`

**`test_app.py`:** Uses `httpx.AsyncClient` with FastAPI's `TestClient`. Mock the `ChainClient` to avoid needing a real chain.

- `test_health` — GET /health → 200
- `test_submit_legitimate` — POST with legitimate project → 200, status APPROVED
- `test_submit_duplicate` — POST with overlapping project → 200, status REJECTED/FLAGGED
- `test_get_project` — GET /projects/{id} → 200 with full response
- `test_list_projects` — GET /projects → 200 with list
- `test_dashboard_stats` — GET /dashboard/stats → 200 with correct counts

---

## 12. Deployment

### 12.1 Local Development

```bash
# Terminal 1: Local blockchain
anvil

# Terminal 2: Deploy contract
cd contracts
PRIVATE_KEY=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80 \
EXTRA_VALIDATOR=0x70997970C51812dc3A010C7d01b50e0d17dc79C8 \
forge script script/Deploy.s.sol --rpc-url http://127.0.0.1:8545 --broadcast
cd ..

# Terminal 3: Backend
RPC_URL=http://127.0.0.1:8545 \
CONTRACT_ADDRESS=0x5FbDB2315678afecb367f032d93F642f64180aa3 \
BACKEND_PRIVATE_KEY=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80 \
VALIDATOR2_PRIVATE_KEY=0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d \
CHAIN_ID=31337 \
USE_FIXTURES=true \
uvicorn backend.app:app --reload --port 8000

# Terminal 4: Frontend
python -m http.server --directory frontend 5173
# Open http://localhost:5173
```

### 12.2 Testnet Deployment (Base Sepolia)

```bash
# 1. Get testnet ETH from faucet
# Base Sepolia: https://www.alchemy.com/faucets/base-sepolia

# 2. Deploy contract
cd contracts
source .env   # Must have PRIVATE_KEY and BASE_SEPOLIA_RPC_URL
forge script script/Deploy.s.sol \
  --rpc-url $BASE_SEPOLIA_RPC_URL \
  --broadcast \
  --verify \
  --etherscan-api-key $BASESCAN_API_KEY
# Note the deployed address from console output

# 3. Run backend pointing to testnet
RPC_URL=$BASE_SEPOLIA_RPC_URL \
CONTRACT_ADDRESS=<deployed_address> \
BACKEND_PRIVATE_KEY=$PRIVATE_KEY \
VALIDATOR2_PRIVATE_KEY=<second_key> \
CHAIN_ID=84532 \
USE_FIXTURES=true \
uvicorn backend.app:app --port 8000

# 4. For production hosting:
# Frontend → Vercel (connect GitHub repo, set frontend/ as root)
# Backend → Render (create web service, set build command, env vars)
```

### 12.3 Vercel Deployment (Frontend)

1. Connect GitHub repo to Vercel
2. Set root directory: `frontend`
3. No build command needed (static HTML)
4. Set environment variable: `VITE_API_URL=https://your-backend.onrender.com`
5. Deploy

### 12.4 Render Deployment (Backend)

1. Create new Web Service on Render
2. Connect GitHub repo
3. Set:
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn backend.app:app --host 0.0.0.0 --port $PORT`
4. Set environment variables: RPC_URL, CONTRACT_ADDRESS, BACKEND_PRIVATE_KEY, VALIDATOR2_PRIVATE_KEY, CHAIN_ID, USE_FIXTURES
5. Deploy

---

## Quick Reference: Key Constants

| Constant | Value | Where Used |
|---|---|---|
| H3 Resolution | 9 | pipeline/geospatial.py, contract cell arrays |
| Attestation Threshold | 2 (of 3) | VeriCarbon.sol |
| Risk LOW threshold | < 0.40 | pipeline/risk_scoring.py |
| Risk HIGH threshold | >= 0.75 | pipeline/risk_scoring.py |
| Verification VERIFIED | share >= 0.80 AND confidence >= 0.85 | pipeline/satellite.py |
| Verification REVIEW | share >= 0.50 AND confidence >= 0.50 | pipeline/satellite.py |
| NDVI threshold | 0.15 increase | pipeline/satellite.py |
| Pixel area (Sentinel-2) | ~0.01 ha (10m × 10m) | pipeline/satellite.py |
| Confidence basis points | 0-10000 (= 0-100%) | VeriCarbon.sol |
| Risk basis points | 0-10000 | VeriCarbon.sol |

---

## Quick Reference: Demo Data for Scenarios

### Scenario A: Legitimate Project
```
project_id:     "FOREST-1042"
name:           "Amazon Reforestation Project"
organization:   "Green Earth Foundation"
country:        "Brazil"
region:         "Amazonas"
claimed_area:   500 ha
registry_ref:   "VERRA:VCS-1042"
expected:       verified_area=412, confidence=0.91, status=VERIFIED
                risk=LOW, no matches found
                → REGISTERED on-chain, claim issued
```

### Scenario B: Duplicate Project
```
project_id:     "GFR-18"
name:           "Amazonia Green Initiative"
organization:   "GreenForest Initiative Ltd"
country:        "Brazil"
region:         "Amazonas"
claimed_area:   480 ha
registry_ref:   "GS:GFR-18"
expected:       verified_area=~410 (same land), confidence=0.90
                entity_similarity=0.964, geo_overlap=0.94
                risk=HIGH (0.87)
                → BLOCKED on-chain (cells already claimed by FOREST-1042)
```

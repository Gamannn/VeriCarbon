"""FastAPI application for VeriCarbon."""
from __future__ import annotations

import logging
from dataclasses import asdict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .chain import ChainClient
from .schemas import (
    ChainStatusOut,
    DuplicateCheckOut,
    DuplicateMatchOut,
    ProjectSubmission,
    SimilarityFeaturesOut,
    SubmitOnchainOut,
    TxReceiptOut,
    VerificationOut,
)
from .services import (
    build_attestation_args,
    build_submission_args,
    run_duplicate_check,
    run_verification,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("vericarbon")

app = FastAPI(title="VeriCarbon API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────────────────────────────────────
# Health / status
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "vericarbon-api"}


@app.get("/chain/status", response_model=ChainStatusOut)
def chain_status() -> ChainStatusOut:
    return ChainStatusOut(**ChainClient().status())


# ──────────────────────────────────────────────────────────────────────────────
# Verification (satellite / fixture)
# ──────────────────────────────────────────────────────────────────────────────
@app.post("/verify", response_model=VerificationOut)
def verify(sub: ProjectSubmission) -> VerificationOut:
    try:
        result = run_verification(sub.project_id, sub.polygon.model_dump(), sub.claimed_area_ha)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        log.exception("verify failed")
        raise HTTPException(status_code=500, detail=f"verification failed: {e}")
    return VerificationOut(**result.to_dict())


# ──────────────────────────────────────────────────────────────────────────────
# Duplicate check (fuzzy entity + geospatial)
# ──────────────────────────────────────────────────────────────────────────────
@app.post("/duplicate-check", response_model=DuplicateCheckOut)
def duplicate_check(sub: ProjectSubmission) -> DuplicateCheckOut:
    matches, highest, cell_count = run_duplicate_check(
        sub.project_id,
        sub.name,
        sub.organization,
        sub.description,
        sub.polygon.model_dump(),
    )
    return DuplicateCheckOut(
        project_id=sub.project_id,
        cell_count=cell_count,
        highest_risk_level=highest,
        matches=[
            DuplicateMatchOut(
                candidate_id=m.candidate_id,
                other_id=m.other_id,
                other_registry=m.other_registry,
                other_registry_ref=m.other_registry_ref,
                risk_score=m.risk_score,
                risk_level=m.risk_level,
                explanation=m.explanation,
                features=SimilarityFeaturesOut(**asdict(m.features)),
            )
            for m in matches
        ],
    )


# ──────────────────────────────────────────────────────────────────────────────
# Full onchain pipeline: submit → verify → attest → (optionally) issue
# ──────────────────────────────────────────────────────────────────────────────
def _append_submitted_cache(sub: ProjectSubmission, tx_hash: str, cell_count: int) -> None:
    """Record a successful submission so the dashboard can show it on reload."""
    import json
    from pathlib import Path

    from .config import get_settings

    cache_path = Path(get_settings().registry_corpus_path).parent / "submitted_cache.json"
    data = {"projects": []}
    if cache_path.exists():
        try:
            data = json.loads(cache_path.read_text())
        except Exception:
            data = {"projects": []}
    data["projects"].append(
        {
            "project_id": sub.project_id,
            "name": sub.name,
            "organization": sub.organization,
            "polygon": sub.polygon.model_dump(),
            "area_ha": sub.claimed_area_ha,
            "tx_hash": tx_hash,
            "cell_count": cell_count,
        }
    )
    try:
        cache_path.write_text(json.dumps(data, indent=2))
    except Exception:
        pass


@app.post("/onchain/submit", response_model=SubmitOnchainOut)
def onchain_submit(sub: ProjectSubmission) -> SubmitOnchainOut:
    """Submit the project to the smart contract. Requires chain configuration."""
    args = build_submission_args(
        sub.project_id,
        sub.polygon.model_dump(),
        sub.claimed_area_ha,
        sub.registry_refs,
    )
    cell_count = len(args["cells_uint64"])
    client = ChainClient()
    try:
        receipt = client.submit_project(
            args["project_id_bytes"],
            args["cells_uint64"],
            args["claimed_area_ha"],
            args["registry_refs_hash"],
        )
        _append_submitted_cache(sub, receipt.tx_hash, cell_count)
        return SubmitOnchainOut(
            project_id=sub.project_id,
            cell_count=cell_count,
            tx=TxReceiptOut(
                tx_hash=receipt.tx_hash,
                block_number=receipt.block_number,
                gas_used=receipt.gas_used,
                status=receipt.status,
            ),
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        log.exception("onchain submit failed")
        return SubmitOnchainOut(project_id=sub.project_id, cell_count=cell_count, error=str(e))


@app.post("/onchain/attest", response_model=TxReceiptOut)
def onchain_attest(sub: ProjectSubmission) -> TxReceiptOut:
    """Run verification and post two attestations (validator1 + validator2).

    After the first attestation from the backend signer, a second attestation
    is posted from VALIDATOR2_PRIVATE_KEY so the contract reaches the 2-of-2
    threshold and transitions the project to Verified.
    """
    try:
        result = run_verification(sub.project_id, sub.polygon.model_dump(), sub.claimed_area_ha)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    args = build_attestation_args(result)
    client = ChainClient()
    try:
        receipt = client.attest_verification(
            args["project_id_bytes"],
            args["dataset_hash"],
            args["model_hash"],
            args["result_hash"],
            args["verified_area_ha"],
            args["confidence_bps"],
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    try:
        client.attest_as_validator2(
            args["project_id_bytes"],
            args["dataset_hash"],
            args["model_hash"],
            args["result_hash"],
            args["verified_area_ha"],
            args["confidence_bps"],
        )
        log.info("Validator2 attestation posted — project should be Verified now")
    except Exception as e:
        log.warning("Validator2 attestation failed (project stays Pending): %s", e)

    return TxReceiptOut(
        tx_hash=receipt.tx_hash,
        block_number=receipt.block_number,
        gas_used=receipt.gas_used,
        status=receipt.status,
    )


@app.get("/onchain/project/{project_id}")
def onchain_project(project_id: str) -> dict:
    import hashlib

    pid = hashlib.sha256(project_id.encode()).digest()
    client = ChainClient()
    try:
        return client.get_project(pid)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"project not found or chain error: {e}")


# ──────────────────────────────────────────────────────────────────────────────
# Registry corpus — so the map can show existing registry entries as overlays
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/registry/projects")
def registry_projects() -> dict:
    """Return the (synthetic) registry corpus as GeoJSON-friendly features."""
    import json
    from pathlib import Path

    from .config import get_settings

    path = Path(get_settings().registry_corpus_path)
    if not path.exists():
        return {"projects": [], "disclaimer": "No registry corpus loaded."}
    data = json.loads(path.read_text())
    out = []
    for p in data.get("projects", []):
        out.append(
            {
                "project_id": p["project_id"],
                "registry": p.get("registry", ""),
                "registry_ref": p.get("registry_ref", ""),
                "name": p.get("name", ""),
                "organization": p.get("organization", ""),
                "polygon": p["polygon"],
                "area_ha": p.get("area_ha"),
            }
        )
    return {
        "projects": out,
        "disclaimer": data.get(
            "_label",
            "Synthetic registry corpus — no claim about any real-world organization.",
        ),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Submitted-on-chain projects — polygons the backend has posted
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/onchain/submitted")
def onchain_submitted() -> dict:
    """List project IDs the backend has submitted this session.

    Note: polygons are *not* stored on-chain (only H3 cell ids). This endpoint
    reads the local submission cache written by the backend so the dashboard
    can echo back what has been submitted and show polygons on the map.
    """
    import json
    from pathlib import Path

    from .config import get_settings

    cache_path = Path(get_settings().registry_corpus_path).parent / "submitted_cache.json"
    if not cache_path.exists():
        return {"projects": []}
    try:
        return json.loads(cache_path.read_text())
    except Exception:
        return {"projects": []}

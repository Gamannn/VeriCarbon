"""End-to-end demo scenarios A and B against a live chain.

Scenario A — legitimate project:
    1. Submit the Amazonia pilot (polygon + claimed area + registry refs).
    2. Run the (fixture) satellite verification pipeline.
    3. Post two validator attestations with matching dataset/model/result hashes.
    4. Issue the carbon claim.
    5. Print the on-chain state and transaction hashes.

Scenario B — duplicate project:
    1. Attempt to submit a renamed project whose polygon overlaps Scenario A.
    2. Expect the smart contract to revert at cell level — this is the
       enforcement that distinguishes VeriCarbon from fuzzy-match-only tools.

Env vars:
    RPC_URL              (e.g. http://127.0.0.1:8545)
    CONTRACT_ADDRESS     (checksum address of the deployed VeriCarbon)
    BACKEND_PRIVATE_KEY  (admin + validator #1)
    VALIDATOR2_PRIVATE_KEY (validator #2 — must already have VALIDATOR_ROLE)
    CHAIN_ID             (default 31337)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from eth_account import Account
from web3 import Web3

from backend.chain import ChainClient
from backend.services import (
    build_attestation_args,
    build_submission_args,
    run_duplicate_check,
    run_verification,
)


AMAZONIA_POLYGON = {
    "type": "Polygon",
    "coordinates": [
        [[-60.02, -3.01], [-59.98, -3.01], [-59.98, -2.98], [-60.02, -2.98], [-60.02, -3.01]]
    ],
}

DUPLICATE_POLYGON = {
    "type": "Polygon",
    "coordinates": [
        [[-60.015, -3.005], [-59.985, -3.005], [-59.985, -2.985], [-60.015, -2.985], [-60.015, -3.005]]
    ],
}


def _hdr(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def _send_with_signer(w3: Web3, contract, account, fn, *, chain_id: int, gas: int = 15_000_000):
    tx = fn.build_transaction(
        {
            "from": account.address,
            "nonce": w3.eth.get_transaction_count(account.address),
            "chainId": chain_id,
            "gas": gas,
        }
    )
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    return tx_hash.hex(), receipt


def _ensure_validator_role(client: ChainClient, address: str, chain_id: int) -> None:
    role = client.contract.functions.VALIDATOR_ROLE().call()
    has_role = client.contract.functions.hasRole(role, address).call()
    if has_role:
        print(f"      {address} already has VALIDATOR_ROLE")
        return
    tx_hash, receipt = _send_with_signer(
        client.w3,
        client.contract,
        client.account,
        client.contract.functions.grantRole(role, address),
        chain_id=chain_id,
        gas=3_000_000,
    )
    assert receipt.status == 1, f"grantRole failed: {tx_hash}"
    print(f"      Granted VALIDATOR_ROLE to {address} (tx {tx_hash})")


def scenario_a(client: ChainClient, validator2: Account, chain_id: int) -> dict:
    _hdr("SCENARIO A — Legitimate project (Amazonia Pilot)")
    pid = "amazonia-pilot-01"

    # 1. Off-chain duplicate pre-check
    matches, highest, cell_count = run_duplicate_check(
        pid, "Amazonia Reforestation Pilot", "GreenForest Inc", "pilot", AMAZONIA_POLYGON
    )
    print(f"[1] Off-chain duplicate pre-check: {len(matches)} matches, highest={highest}, cells={cell_count}")
    for m in matches:
        print(f"      vs {m.other_id} ({m.other_registry}): risk={m.risk_level} ({m.risk_score:.2f})")

    # 2. Ensure validator #2 role
    print(f"[2] Ensuring validator #2 ({validator2.address}) has VALIDATOR_ROLE")
    _ensure_validator_role(client, validator2.address, chain_id)

    # 3. On-chain submission
    args = build_submission_args(pid, AMAZONIA_POLYGON, 500.0, ["VCS-DEMO-SELF-01"])
    r = client.submit_project(
        args["project_id_bytes"],
        args["cells_uint64"],
        args["claimed_area_ha"],
        args["registry_refs_hash"],
    )
    assert r.status == 1, f"submit failed: {r.tx_hash}"
    print(f"[3] submitProject tx: 0x{r.tx_hash} (gas {r.gas_used}, block {r.block_number})")

    # 4. Verification pipeline (fixture mode)
    result = run_verification(pid, AMAZONIA_POLYGON, 500.0)
    print(
        f"[4] Verification: outcome={result.outcome} confidence={result.confidence_bps/100:.2f}% "
        f"vegetated={result.estimated_vegetated_area_ha:.0f} ha / claimed=500 ha"
    )
    print(f"      dataset_hash={result.dataset_hash}")
    print(f"      model_hash  ={result.model_hash}")
    print(f"      result_hash ={result.result_hash}")

    att = build_attestation_args(result)

    # 5a. Attestation #1 from the backend/deployer validator
    r2 = client.attest_verification(
        att["project_id_bytes"],
        att["dataset_hash"],
        att["model_hash"],
        att["result_hash"],
        att["verified_area_ha"],
        att["confidence_bps"],
    )
    assert r2.status == 1, f"attest #1 failed: {r2.tx_hash}"
    print(f"[5a] attestVerification #1 tx: 0x{r2.tx_hash}")

    # 5b. Attestation #2 from validator2 — this triggers finalization to Verified
    tx_hash, rc2 = _send_with_signer(
        client.w3,
        client.contract,
        validator2,
        client.contract.functions.attestVerification(
            att["project_id_bytes"],
            att["dataset_hash"],
            att["model_hash"],
            att["result_hash"],
            att["verified_area_ha"],
            att["confidence_bps"],
        ),
        chain_id=chain_id,
        gas=20_000_000,
    )
    assert rc2.status == 1, f"attest #2 reverted (status 0) tx={tx_hash}"
    print(f"[5b] attestVerification #2 tx: 0x{tx_hash} (gas {rc2.gasUsed})")

    # 6. Issue the claim (state must be Verified)
    r3 = client.issue_claim(att["project_id_bytes"])
    assert r3.status == 1, f"issueClaim failed: {r3.tx_hash}"
    print(f"[6] issueClaim tx: 0x{r3.tx_hash}")

    # 7. Read back project state
    state = client.get_project(att["project_id_bytes"])
    print(f"[7] On-chain state: {state['state']} verified={state['verified_area_ha']} ha "
          f"confidence={state['confidence_bps']/100:.2f}% attestations={state['attestation_count']}")
    assert state["state"] == "Issued", f"expected Issued, got {state['state']}"
    print("[OK] Scenario A complete.")
    return {"state": state, "cells": len(args["cells_uint64"]), "tx_submit": r.tx_hash,
            "tx_attest1": r2.tx_hash, "tx_attest2": tx_hash.replace("0x", ""),
            "tx_issue": r3.tx_hash}


def scenario_b(client: ChainClient) -> dict:
    _hdr("SCENARIO B — Duplicate project (renamed, overlapping polygon)")
    pid = "rio-verde-renamed-02"

    matches, highest, cell_count = run_duplicate_check(
        pid, "Rio Verde Carbon Removal", "EcoAlpha Foundation", "pilot", DUPLICATE_POLYGON
    )
    print(f"[1] Off-chain duplicate check: highest={highest}, cells={cell_count}, matches:")
    for m in matches[:3]:
        print(f"      vs {m.other_id}: risk={m.risk_level} ({m.risk_score:.2f})")
        for reason in m.explanation:
            print(f"           - {reason}")

    args = build_submission_args(pid, DUPLICATE_POLYGON, 450.0, ["VCS-DEMO-SELF-02"])
    print(f"[2] Attempting submitProject with {len(args['cells_uint64'])} cells "
          f"(contract should revert on duplicate cell)")
    try:
        r = client.submit_project(
            args["project_id_bytes"],
            args["cells_uint64"],
            args["claimed_area_ha"],
            args["registry_refs_hash"],
        )
        print(f"[FAIL] submit unexpectedly succeeded: 0x{r.tx_hash}")
        return {"blocked": False}
    except Exception as e:
        msg = str(e)
        print(f"[OK] submit blocked by contract: {msg[:300]}")
        return {"blocked": True, "revert": msg[:400]}


def main() -> int:
    rpc = os.environ.get("RPC_URL")
    addr = os.environ.get("CONTRACT_ADDRESS")
    pk = os.environ.get("BACKEND_PRIVATE_KEY")
    pk2 = os.environ.get("VALIDATOR2_PRIVATE_KEY")
    chain_id = int(os.environ.get("CHAIN_ID", "31337"))
    if not (rpc and addr and pk and pk2):
        print("ERROR: set RPC_URL, CONTRACT_ADDRESS, BACKEND_PRIVATE_KEY, VALIDATOR2_PRIVATE_KEY.")
        return 2

    client = ChainClient()
    print(f"Chain status: {client.status()}")
    validator2 = Account.from_key(pk2)
    print(f"Validator #2 address: {validator2.address}")

    try:
        a = scenario_a(client, validator2, chain_id)
    except Exception as e:
        print(f"[SCENARIO A FAILED] {e}")
        import traceback; traceback.print_exc()
        return 1

    b = scenario_b(client)

    _hdr("SUMMARY")
    print(f"Scenario A: {a['state']['state']} (cells claimed: {a['cells']})")
    print(f"Scenario B: {'duplicate blocked by contract' if b.get('blocked') else 'NOT BLOCKED'}")
    out = ROOT / "docs" / "demo_run.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"scenario_a": a, "scenario_b": b}, default=str, indent=2))
    print(f"Full result written to {out}")
    return 0 if b.get("blocked") else 1


if __name__ == "__main__":
    sys.exit(main())

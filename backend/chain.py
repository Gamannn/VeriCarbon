"""Smart-contract interaction (web3.py)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from eth_account import Account
from web3 import Web3

from .config import get_settings

ARTIFACT = (
    Path(__file__).resolve().parent.parent
    / "contracts"
    / "out"
    / "VeriCarbon.sol"
    / "VeriCarbon.json"
)


@dataclass
class TxReceipt:
    tx_hash: str
    block_number: int
    gas_used: int
    status: int


def _load_abi() -> list:
    if not ARTIFACT.exists():
        raise RuntimeError(
            f"Contract artifact not found at {ARTIFACT}. Run `forge build` first."
        )
    data = json.loads(ARTIFACT.read_text())
    return data["abi"]


class ChainClient:
    """Thin web3 wrapper for the VeriCarbon contract.

    When no RPC / contract address is configured, operations raise
    ``RuntimeError`` with a clear message. The backend's HTTP layer catches
    those and surfaces them as 503 — it does **not** silently mock a success.
    """

    def __init__(self) -> None:
        s = get_settings()
        self.w3 = Web3(Web3.HTTPProvider(s.rpc_url))
        self.contract_address = s.contract_address
        self.account = Account.from_key(s.private_key) if s.private_key else None
        self.abi = _load_abi()
        self.contract = (
            self.w3.eth.contract(address=Web3.to_checksum_address(s.contract_address), abi=self.abi)
            if s.contract_address
            else None
        )

    # ──────────────────── Status ────────────────────
    def is_configured(self) -> bool:
        return bool(self.contract and self.account and self.w3.is_connected())

    def status(self) -> dict:
        connected = False
        try:
            connected = self.w3.is_connected()
        except Exception:
            pass
        return {
            "rpc_url": get_settings().rpc_url,
            "contract_address": get_settings().contract_address,
            "connected": connected,
            "configured": self.is_configured(),
            "signer": self.account.address if self.account else "",
            "chain_id": get_settings().chain_id,
        }

    def _require(self) -> None:
        if not self.is_configured():
            raise RuntimeError(
                "Chain client not configured. Set RPC_URL, CONTRACT_ADDRESS, and "
                "BACKEND_PRIVATE_KEY in .env, deploy the contract, and restart."
            )

    # ──────────────────── Transactions ────────────────────
    def _send(self, fn, *, gas: int = 30_000_000) -> TxReceipt:
        assert self.account is not None
        tx = fn.build_transaction(
            {
                "from": self.account.address,
                "nonce": self.w3.eth.get_transaction_count(self.account.address),
                "chainId": get_settings().chain_id,
                "gas": gas,
            }
        )
        signed = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt.status != 1:
            # Transaction mined but reverted. Try to extract the revert reason by
            # replaying with eth_call at the same block.
            try:
                self.w3.eth.call(
                    {k: tx[k] for k in ("from", "to", "data", "value", "gas") if k in tx},
                    block_identifier=receipt.blockNumber,
                )
            except Exception as e:  # noqa: BLE001
                raise RuntimeError(
                    f"Transaction reverted (tx {tx_hash.hex()}): {e}"
                ) from None
            raise RuntimeError(f"Transaction reverted (tx {tx_hash.hex()}) with no reason data")
        return TxReceipt(
            tx_hash=tx_hash.hex(),
            block_number=receipt.blockNumber,
            gas_used=receipt.gasUsed,
            status=receipt.status,
        )

    def submit_project(
        self,
        project_id: bytes,
        cells_uint64: Iterable[int],
        claimed_area_ha: int,
        registry_refs_hash: bytes,
    ) -> TxReceipt:
        self._require()
        return self._send(
            self.contract.functions.submitProject(
                project_id,
                list(cells_uint64),
                claimed_area_ha,
                registry_refs_hash,
            )
        )

    def attest_verification(
        self,
        project_id: bytes,
        dataset_hash: bytes,
        model_hash: bytes,
        result_hash: bytes,
        verified_area_ha: int,
        confidence_bps: int,
    ) -> TxReceipt:
        self._require()
        return self._send(
            self.contract.functions.attestVerification(
                project_id,
                dataset_hash,
                model_hash,
                result_hash,
                verified_area_ha,
                confidence_bps,
            )
        )

    def flag_project(self, project_id: bytes, reason: str) -> TxReceipt:
        self._require()
        return self._send(self.contract.functions.flagProject(project_id, reason))

    def issue_claim(self, project_id: bytes) -> TxReceipt:
        self._require()
        return self._send(self.contract.functions.issueClaim(project_id))

    # ──────────────────── Reads ────────────────────
    def get_project(self, project_id: bytes) -> dict:
        self._require()
        p = self.contract.functions.getProject(project_id).call()
        state_names = ["None", "Pending", "Flagged", "Verified", "Issued", "Rejected"]
        return {
            "submitter": p[0],
            "state": state_names[p[1]] if 0 <= p[1] < len(state_names) else str(p[1]),
            "state_code": p[1],
            "claimed_area_ha": p[2],
            "verified_area_ha": p[3],
            "confidence_bps": p[4],
            "attestation_count": p[5],
            "submitted_at": p[6],
            "last_updated_at": p[7],
            "dataset_hash": "0x" + p[8].hex() if isinstance(p[8], bytes) else p[8],
            "model_hash": "0x" + p[9].hex() if isinstance(p[9], bytes) else p[9],
            "result_hash": "0x" + p[10].hex() if isinstance(p[10], bytes) else p[10],
        }

    def get_cell_owner(self, cell_uint64: int) -> str:
        self._require()
        owner_bytes = self.contract.functions.getCellOwner(cell_uint64).call()
        return "0x" + owner_bytes.hex() if isinstance(owner_bytes, bytes) else str(owner_bytes)

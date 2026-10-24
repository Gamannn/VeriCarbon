"""Seed the fresh contract with registry corpus entries.

This claims the H3 cells for all corpus projects on-chain so that
overlapping demo submissions (e.g. Amazonia template) get rejected
with CellAlreadyClaimed.

Run from the project root:
    python -I scripts/seed_contract.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.config import get_settings
from backend.chain import ChainClient
from backend.services import project_id_bytes, registry_refs_hash, polygon_to_cells_uint64

CORPUS = ROOT / "pipeline" / "data" / "registry_corpus.json"


def main():
    data = json.loads(CORPUS.read_text())
    projects = data["projects"]
    client = ChainClient()

    if not client.is_configured():
        print("ERROR: Chain client not configured. Check .env")
        sys.exit(1)

    print(f"Seeding {len(projects)} corpus entries onto contract {get_settings().contract_address}\n")

    for p in projects:
        pid = p["project_id"]
        pid_bytes = project_id_bytes(pid)
        cells = polygon_to_cells_uint64(p["polygon"])
        area = int(round(p.get("area_ha", 100)))
        refs_hash = registry_refs_hash([p.get("registry_ref", "")])

        print(f"  {pid}: {len(cells)} H3 cells, {area} ha ... ", end="", flush=True)
        try:
            receipt = client.submit_project(pid_bytes, cells, area, refs_hash)
            print(f"OK  tx={receipt.tx_hash[:16]}...")
        except Exception as e:
            print(f"FAIL  {e}")

    print("\nDone. Corpus cells are now claimed on-chain.")


if __name__ == "__main__":
    main()

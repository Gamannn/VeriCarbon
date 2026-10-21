"""Backend configuration (env-driven, no secrets in code)."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", override=False)


class Settings:
    rpc_url: str = os.environ.get("RPC_URL", "http://127.0.0.1:8545")
    contract_address: str = os.environ.get("CONTRACT_ADDRESS", "")
    private_key: str = os.environ.get("BACKEND_PRIVATE_KEY", "")
    chain_id: int = int(os.environ.get("CHAIN_ID", "31337"))
    satellite_mode: str = os.environ.get("SATELLITE_MODE", "fixture")  # fixture | live
    registry_corpus_path: str = os.environ.get(
        "REGISTRY_CORPUS_PATH", str(ROOT / "pipeline" / "data" / "registry_corpus.json")
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

from __future__ import annotations
import base64
import hashlib
import json
from pathlib import Path
from typing import Optional


class DeviceSync:
    SYNC_DIR = Path(".zenith/sync")
    SYNCTHING_URL = "http://localhost:8384"

    def __init__(self, api_key: str = "", encryption_key: str = ""):
        self._api_key = api_key
        self._enc_key = self._derive_key(encryption_key) if encryption_key else None
        self.enabled = bool(api_key and encryption_key)

    def _derive_key(self, passphrase: str) -> bytes:
        return hashlib.pbkdf2_hmac(
            "sha256", passphrase.encode(), b"zenith-salt-v1", 100_000
        )

    def _encrypt(self, data: str) -> str:
        if not self._enc_key:
            return data
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            import os
            nonce = os.urandom(12)
            aesgcm = AESGCM(self._enc_key)
            ct = aesgcm.encrypt(nonce, data.encode(), None)
            return base64.b64encode(nonce + ct).decode()
        except ImportError:
            return data

    def _decrypt(self, data: str) -> str:
        if not self._enc_key:
            return data
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            raw = base64.b64decode(data.encode())
            nonce, ct = raw[:12], raw[12:]
            aesgcm = AESGCM(self._enc_key)
            return aesgcm.decrypt(nonce, ct, None).decode()
        except Exception:
            return data

    async def push_memory_snapshot(self, memories: list) -> bool:
        if not self.enabled:
            return False
        try:
            self.SYNC_DIR.mkdir(parents=True, exist_ok=True)
            payload = json.dumps({"memories": memories, "version": 1})
            encrypted = self._encrypt(payload)
            snapshot_path = self.SYNC_DIR / "memory_snapshot.enc"
            snapshot_path.write_text(encrypted)
            return True
        except Exception:
            return False

    async def pull_memory_snapshot(self) -> Optional[list]:
        if not self.enabled:
            return None
        try:
            snapshot_path = self.SYNC_DIR / "memory_snapshot.enc"
            if not snapshot_path.exists():
                return None
            encrypted = snapshot_path.read_text()
            decrypted = self._decrypt(encrypted)
            data = json.loads(decrypted)
            return data.get("memories", [])
        except Exception:
            return None

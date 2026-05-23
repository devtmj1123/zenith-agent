from __future__ import annotations
import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List


@dataclass
class StagedItem:
    item_id: str
    content: str
    physics_quantities: dict = field(default_factory=dict)
    confidence: float = 0.0
    source: str = "dream"
    status: str = "pending"
    created_at: float = field(default_factory=time.time)
    zero_error_passed: bool = False
    dimension_check_passed: bool = False


class StagingBuffer:
    BUFFER_PATH = Path(".zenith/staging_buffer.jsonl")

    def __init__(self):
        self.BUFFER_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._active: Dict[str, StagedItem] = {}

    def stage(self, content: str, physics_quantities: dict = None,
              confidence: float = 0.0) -> str:
        item_id = str(uuid.uuid4())[:8]
        item = StagedItem(
            item_id=item_id,
            content=content,
            physics_quantities=physics_quantities or {},
            confidence=confidence,
        )
        self._active[item_id] = item
        self._persist(item)
        return item_id

    def validate(self, item_id: str) -> bool:
        if item_id in self._active:
            self._active[item_id].status = "validated"
            self._active[item_id].zero_error_passed = True
            return True
        return False

    def reject(self, item_id: str, reason: str) -> None:
        if item_id in self._active:
            self._active[item_id].status = "rejected"

    def get_validated(self) -> List[StagedItem]:
        return [i for i in self._active.values() if i.status == "validated"]

    def clear_committed(self, item_ids: List[str]) -> None:
        for item_id in item_ids:
            self._active.pop(item_id, None)

    def dump_suspended(self) -> None:
        pending = [i for i in self._active.values() if i.status == "pending"]
        with open(self.BUFFER_PATH, "a") as f:
            for item in pending:
                f.write(json.dumps({
                    "item_id": item.item_id, "content": item.content,
                    "confidence": item.confidence, "timestamp": time.time(),
                    "status": "suspended"
                }) + "\n")

    def _persist(self, item: StagedItem) -> None:
        with open(self.BUFFER_PATH, "a") as f:
            f.write(json.dumps({
                "item_id": item.item_id, "content": item.content[:200],
                "confidence": item.confidence, "source": item.source,
            }) + "\n")

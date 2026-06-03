"""Sandbox — Copy-on-Write virtual filesystem with permission gate and entropy brake."""
from sandbox.cow_projector import CowProjector, ShadowEntry, ShadowStatus
from sandbox.permission_gate import PermissionGate, Decision, GateResult
from sandbox.entropy_brake import EntropyBrake, Reversibility, BrakeResult
from sandbox.shadow_commit import ShadowCommitManager
from sandbox.audit_log import AuditLog

__all__ = [
    "CowProjector", "ShadowEntry", "ShadowStatus",
    "PermissionGate", "Decision", "GateResult",
    "EntropyBrake", "Reversibility", "BrakeResult",
    "ShadowCommitManager",
    "AuditLog",
]

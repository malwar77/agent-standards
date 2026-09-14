"""Optional hard enforcement for standards you mark `critical: true`.

Re-runs the deterministic miner for each critical approved standard and fails
(exit 1) if the CURRENT consistency in the codebase has dropped more than
`tolerance` below the consistency recorded when the standard was approved.

Advisory standards are never enforced — only explicit opt-in via `critical`.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..discover.ast_mine import discover
from ..index.store import Store


@dataclass
class EnforceResult:
    passed: bool
    checked: list  # [(standard, recorded, current, ok)]

    def report(self) -> str:
        lines = []
        for std, recorded, current, ok in self.checked:
            mark = "PASS" if ok else "FAIL"
            lines.append(f"{mark}  {std.id}: recorded {recorded:.0%}, "
                         f"now {current:.0%}")
        if not self.checked:
            lines.append("No critical approved standards to enforce.")
        return "\n".join(lines)


def enforce(root: str, store: Store, tolerance: float = 0.05) -> EnforceResult:
    critical = [s for s in store.load_all(statuses=("approved",))
                if s.critical]
    if not critical:
        return EnforceResult(passed=True, checked=[])

    strong, _ = discover(root, min_observations=1)
    current_by_id = {s.id: s for s in strong}
    checked, passed = [], True
    for std in critical:
        rec = std.evidence.consistency if std.evidence else 0.0
        cur_std = current_by_id.get(std.id)
        cur = cur_std.evidence.consistency if cur_std and cur_std.evidence else 0.0
        ok = cur >= rec - tolerance
        checked.append((std, rec, cur, ok))
        if not ok:
            passed = False
    return EnforceResult(passed=passed, checked=checked)

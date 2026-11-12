"""The audit log: a plain list of every decision the gateway made.

Nothing fancy on purpose. A production gateway would write these
records to a durable store; here they live in memory so the demo can
print them and the tests can assert on them. What matters is the
invariant: every attempt -- allowed, denied, or waiting on approval
-- gets exactly one entry, in order, with the reason attached. If a
call is not in the log, it did not happen through the gateway.
"""

from __future__ import annotations

from datetime import datetime, timezone


class AuditLog:
    def __init__(self) -> None:
        self.entries: list = []

    def record(
        self,
        *,
        tool: str,
        arguments: dict,
        actor: str,
        verdict: str,
        reasons: list,
    ) -> dict:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "actor": actor,
            "tool": tool,
            "arguments": dict(arguments),
            "verdict": verdict,
            "reasons": list(reasons),
        }
        self.entries.append(entry)
        return entry

    def __len__(self) -> int:
        return len(self.entries)

    def __iter__(self):
        return iter(self.entries)

"""The three things a gateway can say about a proposed tool call.

Keeping the verdict this small is deliberate. An agent does not need
a paragraph of policy theory -- it needs to know whether to proceed,
stop, or go and get a human. The reasons list is there for the audit
log and for the human who reviews it later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Verdict(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    NEEDS_APPROVAL = "needs-approval"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


@dataclass(frozen=True)
class Decision:
    """One gateway decision, with the reasons a human can read later."""

    verdict: Verdict
    reasons: list = field(default_factory=list)

    @property
    def allowed(self) -> bool:
        return self.verdict is Verdict.ALLOW

    def __str__(self) -> str:
        detail = "; ".join(self.reasons) if self.reasons else "no reason recorded"
        return f"{self.verdict}: {detail}"

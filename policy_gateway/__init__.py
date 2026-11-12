"""A deterministic policy gateway for AI agents.

The problem, in one sentence: an agent holding a direct API key can
issue a $10,000 refund with nobody approving it, because
authentication is not authorization.

This package sits between an agent and the tools it wants to call and
decides, before anything executes, whether the call may go ahead.
Every decision is one of three verdicts -- allow, deny, or
needs-approval -- and every attempt lands in an audit log.

Zero dependencies, standard library only, Python 3.10+.
"""

from policy_gateway.audit import AuditLog
from policy_gateway.decisions import Decision, Verdict
from policy_gateway.gateway import PolicyError, PolicyGateway
from policy_gateway.rules import DEFAULT_POLICY, Rule

__all__ = [
    "AuditLog",
    "DEFAULT_POLICY",
    "Decision",
    "PolicyError",
    "PolicyGateway",
    "Rule",
    "Verdict",
]

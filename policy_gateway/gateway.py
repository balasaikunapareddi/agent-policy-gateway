"""The gateway: decide first, execute second, log everything.

One entry point, one order of checks, no exceptions to the order:

1. Unknown tool -> deny. The gateway is an allow-list; anything it
   does not know about is denied by default.
2. Role -> deny. A caller outside the tool's allowed roles is refused
   outright, approval or not.
3. Deny-list -> deny. Blocked values (sanctioned accounts, protected
   customers) are refused no matter who asks.
4. Amount cap -> deny. Some numbers are never sane, even approved.
5. Custom rule check -> deny, with the rule's own reason.
6. Approval -> needs-approval. The call is fine except nobody has
   signed off yet. This is not a denial; it is a pause.
7. Otherwise -> allow, and the call goes to the API.

Checks 2-5 run before the approval check on purpose: an approval
must never rescue a call that is wrong on its merits. That is the
$10,000 refund lesson -- "someone approved it" is not a defence when
the amount itself is absurd.

The gateway also enriches the arguments with the context the rules
need (the order's total, today's transfer total) so rule authors
never have to reach into the API themselves.
"""

from __future__ import annotations

from policy_gateway.api import ACCOUNTS, CUSTOMERS, ORDERS
from policy_gateway.audit import AuditLog
from policy_gateway.decisions import Decision, Verdict
from policy_gateway.rules import DEFAULT_POLICY, rules_by_tool

DAILY_TRANSFER_CAP = 2000.00


class PolicyError(Exception):
    """Raised when the gateway refuses a call (deny or needs-approval)."""


class PolicyGateway:
    def __init__(self, api, api_key: str, policy=DEFAULT_POLICY) -> None:
        self.api = api
        self.headers = {"x-api-key": api_key}
        self.rules = rules_by_tool(policy)
        self.audit_log = AuditLog()
        self._daily_transfer_total = 0.0

    # -- decision -----------------------------------------------------

    def decide(
        self,
        tool: str,
        arguments: dict,
        *,
        actor: str = "agent",
        approved: bool = False,
    ) -> Decision:
        """Decide a proposed call without executing anything."""
        args = self._enrich(tool, arguments)
        reasons = []

        rule = self.rules.get(tool)
        if rule is None:
            return Decision(Verdict.DENY, [f"unknown tool: {tool}"])

        if rule.allowed_roles and actor not in rule.allowed_roles:
            reasons.append(
                f"role '{actor}' may not call {tool}; "
                f"allowed roles: {', '.join(rule.allowed_roles)}"
            )
            return Decision(Verdict.DENY, reasons)

        for field_name, blocked in rule.blocked_values.items():
            if args.get(field_name) in blocked:
                reasons.append(
                    f"{field_name} {args.get(field_name)!r} is on the deny-list "
                    f"for {tool}"
                )
                return Decision(Verdict.DENY, reasons)

        if rule.max_amount is not None:
            amount = args.get(rule.amount_field)
            if amount is not None and amount > rule.max_amount:
                reasons.append(
                    f"amount {amount} exceeds the {rule.max_amount} cap "
                    f"for {tool}"
                )
                return Decision(Verdict.DENY, reasons)

        if rule.check is not None:
            problem = rule.check(args)
            if problem is not None:
                return Decision(Verdict.DENY, [problem])

        if rule.requires_approval and not approved:
            return Decision(
                Verdict.NEEDS_APPROVAL,
                [f"{tool} has side effects and needs approval"],
            )

        return Decision(Verdict.ALLOW, ["all policy checks passed"])

    # -- enforcement --------------------------------------------------

    def call_tool(
        self,
        name: str,
        approved: bool = False,
        role: str = "agent",
        **arguments,
    ):
        """Enforce the decision, then dispatch to the API if allowed.

        Denied calls and calls waiting on approval raise PolicyError
        and never reach the API. Allowed calls return the API's
        (status, body) pair. Every attempt is audited exactly once.
        """
        decision = self.decide(name, arguments, actor=role, approved=approved)
        self.audit_log.record(
            tool=name,
            arguments=arguments,
            actor=role,
            verdict=decision.verdict.value,
            reasons=decision.reasons,
        )
        if not decision.allowed:
            raise PolicyError(str(decision))
        result = self._dispatch(name, arguments)
        if name == "transfer_funds":
            self._daily_transfer_total += arguments["amount"]
        return result

    def _dispatch(self, name: str, arguments: dict):
        if name == "get_order":
            return self.api.get_order(arguments["order_id"], self.headers)
        if name == "create_refund":
            return self.api.create_refund(
                arguments["order_id"], arguments["amount"], self.headers
            )
        if name == "transfer_funds":
            return self.api.transfer_funds(
                arguments["from_account"],
                arguments["to_account"],
                arguments["amount"],
                self.headers,
            )
        if name == "purge_customer_data":
            return self.api.purge_customer_data(
                arguments["customer_id"], self.headers
            )
        raise PolicyError(f"unknown tool: {name}")  # pragma: no cover

    # -- helpers ------------------------------------------------------

    def _enrich(self, tool: str, arguments: dict) -> dict:
        """Add the context rules need, without mutating the caller's dict."""
        args = dict(arguments)
        if tool == "create_refund":
            order = ORDERS.get(args.get("order_id"))
            if order is not None:
                args["_order_total"] = order["total"]
        if tool == "transfer_funds":
            args["_daily_transfer_total"] = self._daily_transfer_total
            args["_daily_transfer_cap"] = DAILY_TRANSFER_CAP
        if tool == "purge_customer_data":
            customer = CUSTOMERS.get(args.get("customer_id"))
            if customer is not None:
                args["_customer_protected"] = customer["protected"]
        return args

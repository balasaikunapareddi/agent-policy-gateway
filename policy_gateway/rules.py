"""Policy rules, written as data instead of nested if-statements.

A Rule describes one tool: who may call it, whether a human has to
approve first, and what limits apply to its arguments. The gateway
reads these rules in a fixed order (see gateway.py) and the first
rule that says "no" wins.

Adding a new tool means adding one Rule here -- no new code path in
the gateway itself. That is the whole point of policy-as-code: the
rules you argue about in review are visible in one place, in plain
data, instead of scattered through request handlers.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Rule:
    """What the gateway enforces for one tool.

    Attributes:
        tool: The tool name this rule governs.
        requires_approval: A human must approve the call before it
            runs. Reads never need this; anything that moves money
            or destroys data does.
        allowed_roles: Roles that may call this tool at all. Empty
            means any authenticated caller. A role outside this list
            is denied outright, approval or not.
        max_amount: Upper bound for the numeric argument named by
            ``amount_field``. Amounts above it are denied even with
            approval -- some numbers are never sane, no matter who
            signed off.
        amount_field: Which argument the cap applies to.
        blocked_values: Argument values that are always denied, as
            ``{field_name: {blocked, values}}``. Used for deny-lists,
            e.g. sanctioned accounts or protected customers.
        check: An optional extra check, ``check(arguments) -> str |
            None``. Return a reason string to deny the call, or None
            to pass. This is the escape hatch for rules that do not
            fit the fields above -- keep it small and pure.
    """

    tool: str
    requires_approval: bool = False
    allowed_roles: tuple = ()
    max_amount: float | None = None
    amount_field: str = "amount"
    blocked_values: dict = field(default_factory=dict)
    check: object = None  # Callable[[dict], str | None] | None


def _refund_within_order_total(arguments: dict) -> str | None:
    """A refund can never exceed what the order was worth."""
    order_total = arguments.get("_order_total")
    amount = arguments.get("amount")
    if order_total is None:
        return f"no such order: {arguments.get('order_id')}"
    if amount is None:
        return None
    if amount <= 0:
        return f"refund amount {amount} must be positive"
    if amount > order_total:
        return (
            f"refund amount {amount} exceeds order total {order_total} "
            f"for order {arguments.get('order_id')}"
        )
    return None


def _purge_protected_customer(arguments: dict) -> str | None:
    """Customers under a legal hold can never be purged."""
    if arguments.get("_customer_protected"):
        return (
            f"customer {arguments.get('customer_id')} is protected "
            f"(legal hold) and cannot be purged"
        )
    return None


def _transfer_within_daily_cap(arguments: dict) -> str | None:
    """Transfers also respect a running daily total, not just one call."""
    daily_total = arguments.get("_daily_transfer_total", 0)
    daily_cap = arguments.get("_daily_transfer_cap")
    amount = arguments.get("amount")
    if daily_cap is None or amount is None:
        return None
    if daily_total + amount > daily_cap:
        return (
            f"transfer of {amount} would push today's total to "
            f"{daily_total + amount}, over the daily cap of {daily_cap}"
        )
    return None


# The policy this repo ships with. Three tools, three different risk
# profiles, all visible on one screen.
DEFAULT_POLICY: tuple = (
    # Read-only. The API's own auth is enough; no approval, no cap.
    Rule(tool="get_order"),
    # Money out. Needs approval, needs a support or finance role, and
    # can never exceed the order's total -- an absurd refund is denied
    # even when somebody approved it.
    Rule(
        tool="create_refund",
        requires_approval=True,
        allowed_roles=("support", "finance"),
        check=_refund_within_order_total,
    ),
    # Money moved. Needs approval, finance role only, $1,000 per
    # transfer, $2,000 a day, and never to a blocked account.
    Rule(
        tool="transfer_funds",
        requires_approval=True,
        allowed_roles=("finance",),
        max_amount=1000,
        blocked_values={"to_account": {"ACCT-BLOCKED", "ACCT-SANCTIONED"}},
        check=_transfer_within_daily_cap,
    ),
    # Data destroyed. Needs approval and the admin role, and some
    # customers are protected from deletion no matter who asks.
    Rule(
        tool="purge_customer_data",
        requires_approval=True,
        allowed_roles=("admin",),
        check=_purge_protected_customer,
    ),
)


def rules_by_tool(policy: tuple = DEFAULT_POLICY) -> dict:
    """Index a policy tuple by tool name for the gateway to look up."""
    return {rule.tool: rule for rule in policy}

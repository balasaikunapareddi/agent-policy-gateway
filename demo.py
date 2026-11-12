"""Run the whole story in one command: python demo.py

The setup is the same in every scene: an agent wants to do something
to a small orders/payments API. First it calls the API directly, the
way an agent holding an API key would. Then the same calls go through
the policy gateway.

The refund scene is the one from the LinkedIn post that started this
project: order A-103, worth $24.50. The transfer and purge scenes are
the same idea with different rules -- a money move with caps and a
deny-list, and a destructive delete that only an admin may approve.

No network, no API key to a real service, no dependencies.
"""

from policy_gateway import PolicyError, PolicyGateway
from policy_gateway.api import NativeAPI
from policy_gateway.direct import DirectClient

API_KEY = "demo-key"


def _try(label, fn):
    """Run one call and print what happened, success or refusal."""
    try:
        status, body = fn()
        print(f"  {label}: {status} {body}")
    except PolicyError as exc:
        print(f"  {label}: DENIED -- {exc}")


def main():
    print("=== 1. Direct: the agent holds the API key ===\n")
    api = NativeAPI(API_KEY)
    direct = DirectClient(api, API_KEY)
    _try("refund $24.50 on A-103",
         lambda: direct.call_tool("create_refund", order_id="A-103", amount=24.50))
    _try("refund $10,000 on A-103, nobody approved it",
         lambda: direct.call_tool("create_refund", order_id="A-103", amount=10000))
    _try("transfer $5,000 to a blocked account",
         lambda: direct.call_tool("transfer_funds", from_account="ACCT-OPERATING",
                                  to_account="ACCT-BLOCKED", amount=5000))
    print("  Audit trail of who did what and why: none")
    print(f"  What the API actually did: {len(api.refunds)} refunds, "
          f"{len(api.transfers)} transfers\n")

    print("=== 2. Behind the gateway: refunds ===\n")
    api = NativeAPI(API_KEY)
    gateway = PolicyGateway(api, API_KEY)
    _try("refund $24.50, no approval",
         lambda: gateway.call_tool("create_refund", order_id="A-103", amount=24.50,
                                   role="support"))
    _try("refund $10,000, approved",
         lambda: gateway.call_tool("create_refund", order_id="A-103", amount=10000,
                                   approved=True, role="support"))
    _try("refund $24.50, approved, support role",
         lambda: gateway.call_tool("create_refund", order_id="A-103", amount=24.50,
                                   approved=True, role="support"))
    print(f"  Refunds the API actually processed: {len(api.refunds)}\n")

    print("=== 3. Behind the gateway: money transfers ===\n")
    _try("transfer $500 to payroll, approved, finance role",
         lambda: gateway.call_tool("transfer_funds", from_account="ACCT-OPERATING",
                                   to_account="ACCT-PAYROLL", amount=500,
                                   approved=True, role="finance"))
    _try("transfer $5,000, approved, finance role (over the $1,000 cap)",
         lambda: gateway.call_tool("transfer_funds", from_account="ACCT-OPERATING",
                                   to_account="ACCT-PAYROLL", amount=5000,
                                   approved=True, role="finance"))
    _try("transfer $100 to a blocked account, approved, finance role",
         lambda: gateway.call_tool("transfer_funds", from_account="ACCT-OPERATING",
                                   to_account="ACCT-BLOCKED", amount=100,
                                   approved=True, role="finance"))
    _try("transfer $1,000, approved (daily total now $1,500 of $2,000)",
         lambda: gateway.call_tool("transfer_funds", from_account="ACCT-OPERATING",
                                   to_account="ACCT-PAYROLL", amount=1000,
                                   approved=True, role="finance"))
    _try("transfer $600, approved (would push today to $2,100, over the cap)",
         lambda: gateway.call_tool("transfer_funds", from_account="ACCT-OPERATING",
                                   to_account="ACCT-PAYROLL", amount=600,
                                   approved=True, role="finance"))
    _try("transfer $500, no approval",
         lambda: gateway.call_tool("transfer_funds", from_account="ACCT-OPERATING",
                                   to_account="ACCT-PAYROLL", amount=500,
                                   role="finance"))
    print(f"  Transfers the API actually processed: {len(api.transfers)}\n")

    print("=== 4. Behind the gateway: purging customer data ===\n")
    _try("purge CUST-1042, approved, but as a support agent",
         lambda: gateway.call_tool("purge_customer_data", customer_id="CUST-1042",
                                   approved=True, role="support"))
    _try("purge CUST-VIP-001, approved, admin (customer under legal hold)",
         lambda: gateway.call_tool("purge_customer_data", customer_id="CUST-VIP-001",
                                   approved=True, role="admin"))
    _try("purge CUST-1042, approved, admin",
         lambda: gateway.call_tool("purge_customer_data", customer_id="CUST-1042",
                                   approved=True, role="admin"))
    print(f"  Customers the API actually purged: {api.purged_customers}\n")

    print("=== 5. Unknown tools are denied by default ===\n")
    _try("call 'launch_missiles'",
         lambda: gateway.call_tool("launch_missiles", approved=True, role="admin"))
    print()

    print("=== 6. The audit log: every attempt, in order ===\n")
    for entry in gateway.audit_log:
        print(f"  [{entry['timestamp']}] {entry['actor']:8} "
              f"{entry['tool']:20} {entry['verdict']:15} "
              f"{'; '.join(entry['reasons'])}")
    print()
    print("Takeaway: the agent proposes, the system decides. The gateway")
    print("never re-implements the API -- it only stands in front of it")
    print("and says allow, deny, or go and get a human.")


if __name__ == "__main__":
    main()

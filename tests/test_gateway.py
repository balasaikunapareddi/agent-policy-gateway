"""Tests for the policy gateway.

Each test states one promise the gateway makes, in plain terms.
Run them with:  python -m unittest discover -s tests -v
"""

import unittest

from policy_gateway import PolicyError, PolicyGateway, Verdict
from policy_gateway.api import NativeAPI
from policy_gateway.direct import DirectClient

KEY = "demo-key"


class DirectPathTests(unittest.TestCase):
    """The gap the gateway closes: the API alone cannot say no."""

    def setUp(self):
        self.api = NativeAPI(KEY)
        self.client = DirectClient(self.api, KEY)

    def test_direct_refund_succeeds_without_any_approval(self):
        status, _ = self.client.call_tool(
            "create_refund", order_id="A-103", amount=24.50)
        self.assertEqual(status, 201)

    def test_direct_path_also_lets_an_absurd_refund_through(self):
        status, _ = self.client.call_tool(
            "create_refund", order_id="A-103", amount=10000)
        self.assertEqual(status, 201)

    def test_direct_path_lets_a_blocked_transfer_through(self):
        status, _ = self.client.call_tool(
            "transfer_funds", from_account="ACCT-OPERATING",
            to_account="ACCT-BLOCKED", amount=5000)
        self.assertEqual(status, 201)


class RefundTests(unittest.TestCase):
    def setUp(self):
        self.api = NativeAPI(KEY)
        self.gateway = PolicyGateway(self.api, KEY)

    def test_unapproved_high_value_action_is_denied(self):
        with self.assertRaises(PolicyError):
            self.gateway.call_tool(
                "create_refund", order_id="A-103", amount=24.50,
                role="support")
        # The refusal happened before the API was ever touched.
        self.assertEqual(self.api.refunds, [])

    def test_decide_reports_needs_approval_instead_of_denying_outright(self):
        decision = self.gateway.decide(
            "create_refund", {"order_id": "A-103", "amount": 24.50},
            actor="support", approved=False)
        self.assertEqual(decision.verdict, Verdict.NEEDS_APPROVAL)

    def test_approved_valid_action_is_allowed(self):
        status, body = self.gateway.call_tool(
            "create_refund", order_id="A-103", amount=24.50,
            approved=True, role="support")
        self.assertEqual(status, 201)
        self.assertEqual(body["status"], "refunded")
        self.assertEqual(len(self.api.refunds), 1)

    def test_absurd_amount_is_denied_even_with_approval(self):
        # The $10,000 refund, approved by a support agent, still fails:
        # no order is worth that much, so no approval can rescue it.
        with self.assertRaises(PolicyError):
            self.gateway.call_tool(
                "create_refund", order_id="A-103", amount=10000,
                approved=True, role="support")
        self.assertEqual(self.api.refunds, [])

    def test_refund_for_an_unknown_order_is_denied(self):
        with self.assertRaises(PolicyError):
            self.gateway.call_tool(
                "create_refund", order_id="A-999", amount=10,
                approved=True, role="support")
        self.assertEqual(self.api.refunds, [])

    def test_wrong_role_is_denied_even_with_approval(self):
        with self.assertRaises(PolicyError):
            self.gateway.call_tool(
                "create_refund", order_id="A-103", amount=24.50,
                approved=True, role="agent")
        self.assertEqual(self.api.refunds, [])


class TransferTests(unittest.TestCase):
    def setUp(self):
        self.api = NativeAPI(KEY)
        self.gateway = PolicyGateway(self.api, KEY)

    def _transfer(self, amount, to="ACCT-PAYROLL", **kwargs):
        kwargs.setdefault("approved", True)
        kwargs.setdefault("role", "finance")
        return self.gateway.call_tool(
            "transfer_funds", from_account="ACCT-OPERATING",
            to_account=to, amount=amount, **kwargs)

    def test_approved_transfer_within_cap_is_allowed(self):
        status, _ = self._transfer(500)
        self.assertEqual(status, 201)
        self.assertEqual(len(self.api.transfers), 1)

    def test_transfer_over_the_per_call_cap_is_denied_even_approved(self):
        with self.assertRaises(PolicyError):
            self._transfer(5000)
        self.assertEqual(self.api.transfers, [])

    def test_transfer_to_a_blocked_account_is_denied(self):
        with self.assertRaises(PolicyError):
            self._transfer(100, to="ACCT-BLOCKED")
        with self.assertRaises(PolicyError):
            self._transfer(100, to="ACCT-SANCTIONED")
        self.assertEqual(self.api.transfers, [])

    def test_daily_cap_counts_successful_transfers(self):
        self._transfer(1000)
        self._transfer(1000)
        # $2,000 already moved today; one more dollar is too many.
        with self.assertRaises(PolicyError):
            self._transfer(1)
        self.assertEqual(len(self.api.transfers), 2)

    def test_unapproved_transfer_is_denied(self):
        with self.assertRaises(PolicyError):
            self._transfer(100, approved=False)
        self.assertEqual(self.api.transfers, [])

    def test_non_finance_role_cannot_transfer(self):
        with self.assertRaises(PolicyError):
            self._transfer(100, role="support")
        self.assertEqual(self.api.transfers, [])


class PurgeTests(unittest.TestCase):
    def setUp(self):
        self.api = NativeAPI(KEY)
        self.gateway = PolicyGateway(self.api, KEY)

    def test_purge_needs_the_admin_role(self):
        with self.assertRaises(PolicyError):
            self.gateway.call_tool(
                "purge_customer_data", customer_id="CUST-1042",
                approved=True, role="support")
        self.assertEqual(self.api.purged_customers, [])

    def test_admin_with_approval_can_purge_an_ordinary_customer(self):
        status, body = self.gateway.call_tool(
            "purge_customer_data", customer_id="CUST-1042",
            approved=True, role="admin")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "purged")

    def test_protected_customer_is_denied_even_for_admin(self):
        with self.assertRaises(PolicyError):
            self.gateway.call_tool(
                "purge_customer_data", customer_id="CUST-VIP-001",
                approved=True, role="admin")
        self.assertEqual(self.api.purged_customers, [])


class DefaultDenyTests(unittest.TestCase):
    def setUp(self):
        self.api = NativeAPI(KEY)
        self.gateway = PolicyGateway(self.api, KEY)

    def test_unknown_action_is_denied_by_default(self):
        decision = self.gateway.decide(
            "launch_missiles", {}, actor="admin", approved=True)
        self.assertEqual(decision.verdict, Verdict.DENY)
        with self.assertRaises(PolicyError):
            self.gateway.call_tool(
                "launch_missiles", approved=True, role="admin")

    def test_read_only_calls_need_no_approval(self):
        status, body = self.gateway.call_tool("get_order", order_id="A-102")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "shipped")


class AuditLogTests(unittest.TestCase):
    def setUp(self):
        self.api = NativeAPI(KEY)
        self.gateway = PolicyGateway(self.api, KEY)

    def test_audit_log_records_every_attempt(self):
        attempts = [
            lambda: self.gateway.call_tool(
                "create_refund", order_id="A-103", amount=24.50,
                role="support"),                       # needs approval
            lambda: self.gateway.call_tool(
                "create_refund", order_id="A-103", amount=10000,
                approved=True, role="support"),        # absurd
            lambda: self.gateway.call_tool(
                "create_refund", order_id="A-103", amount=24.50,
                approved=True, role="support"),        # allowed
            lambda: self.gateway.call_tool(
                "launch_missiles", approved=True, role="admin"),  # unknown
        ]
        for attempt in attempts:
            try:
                attempt()
            except PolicyError:
                pass
        self.assertEqual(len(self.gateway.audit_log), 4)
        verdicts = [e["verdict"] for e in self.gateway.audit_log]
        self.assertEqual(
            verdicts,
            ["needs-approval", "deny", "allow", "deny"])
        # Every entry carries the reason, so a reviewer can see why.
        for entry in self.gateway.audit_log:
            self.assertTrue(entry["reasons"])
            self.assertIn("tool", entry)
            self.assertIn("actor", entry)
            self.assertIn("timestamp", entry)

    def test_denied_calls_never_reach_the_api(self):
        with self.assertRaises(PolicyError):
            self.gateway.call_tool(
                "create_refund", order_id="A-103", amount=10000,
                approved=True, role="support")
        self.assertEqual(self.api.refunds, [])
        # ...but the attempt is still in the log.
        self.assertEqual(len(self.gateway.audit_log), 1)


if __name__ == "__main__":
    unittest.main()

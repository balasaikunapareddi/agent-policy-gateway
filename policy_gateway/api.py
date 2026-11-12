"""The downstream system the gateway protects -- a small mock API.

This stands in for a real orders/payments service. It already has
API-key authentication, and it already returns sensible responses.
What it deliberately does NOT do is ask whether a caller *should* be
allowed to do what it is doing: any authenticated caller can refund
any amount, move any sum, or purge any customer, and nothing records
who asked or why.

That gap is the gateway's job, not the API's. The gateway never
re-implements the API; it only decides whether a call may reach it.
"""

from __future__ import annotations

# Local mock data. No network, no database, no API key to a real service.
ORDERS = {
    "A-102": {"status": "shipped", "total": 59.99},
    "A-103": {"status": "delivered", "total": 24.50},
}

ACCOUNTS = {
    "ACCT-OPERATING": {"balance": 50_000.00},
    "ACCT-PAYROLL": {"balance": 12_000.00},
    "ACCT-BLOCKED": {"balance": 0.00},
    "ACCT-SANCTIONED": {"balance": 0.00},
}

CUSTOMERS = {
    "CUST-1042": {"name": "Regular customer", "protected": False},
    "CUST-VIP-001": {"name": "VIP customer, under legal hold", "protected": True},
}


class NativeAPI:
    """The existing API, exactly as an agent would find it."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self.refunds: list = []  # what the API itself processed
        self.transfers: list = []
        self.purged_customers: list = []

    def _authorized(self, headers: dict) -> bool:
        return headers.get("x-api-key") == self._api_key

    def get_order(self, order_id: str, headers: dict):
        if not self._authorized(headers):
            return 401, {"error": "invalid api key"}
        order = ORDERS.get(order_id)
        if order is None:
            return 404, {"error": f"no such order: {order_id}"}
        return 200, {"order_id": order_id, **order}

    def create_refund(self, order_id: str, amount: float, headers: dict):
        # Checks auth and that the order exists. Does NOT check the
        # amount, the caller's role, or whether anyone approved it.
        if not self._authorized(headers):
            return 401, {"error": "invalid api key"}
        if order_id not in ORDERS:
            return 404, {"error": f"no such order: {order_id}"}
        refund = {"order_id": order_id, "amount": amount, "status": "refunded"}
        self.refunds.append(refund)
        return 201, refund

    def transfer_funds(self, from_account: str, to_account: str,
                       amount: float, headers: dict):
        # Same story: auth only. No caps, no deny-list, no approval.
        if not self._authorized(headers):
            return 401, {"error": "invalid api key"}
        if from_account not in ACCOUNTS or to_account not in ACCOUNTS:
            return 404, {"error": "unknown account"}
        transfer = {
            "from_account": from_account,
            "to_account": to_account,
            "amount": amount,
            "status": "transferred",
        }
        self.transfers.append(transfer)
        return 201, transfer

    def purge_customer_data(self, customer_id: str, headers: dict):
        if not self._authorized(headers):
            return 401, {"error": "invalid api key"}
        if customer_id not in CUSTOMERS:
            return 404, {"error": f"no such customer: {customer_id}"}
        self.purged_customers.append(customer_id)
        return 200, {"customer_id": customer_id, "status": "purged"}

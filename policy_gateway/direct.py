"""The unguarded path: an agent calling the API directly.

This is what the gateway exists to prevent. The agent holds the API
key, reads the tool manual, and calls the endpoints straight -- no
approval, no caps, no audit trail. For read-only tools on a mature
API that is often fine. For anything that moves money or destroys
data, it is how a $10,000 refund nobody approved sails through with
a 201 and a smile.

Kept here so the demo can show both paths against the same API, with
the same key, in the same run.
"""

from __future__ import annotations


class DirectClient:
    """Calls the native API exactly as its manual describes."""

    def __init__(self, api, api_key: str) -> None:
        self.api = api
        self.headers = {"x-api-key": api_key}

    def call_tool(self, name: str, **arguments):
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
        raise ValueError(f"tool not in manual: {name}")

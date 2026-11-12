# Changelog

## v0.1.0 — 2026-11-12

First release.

- Deterministic policy gateway in zero-dependency Python: `decide()` returns
  allow / deny / needs-approval, `call_tool()` enforces it, and every
  attempt lands in an audit log.
- Declarative rules (`Rule` in `policy_gateway/rules.py`): approval,
  roles, amount caps, deny-lists, and custom checks, evaluated in a
  fixed order with deny-by-default for unknown tools.
- Four tools in the default policy: `get_order` (read-only),
  `create_refund` (approval + refund ≤ order total),
  `transfer_funds` (approval + finance role + $1,000 per transfer +
  $2,000 daily cap + blocked accounts), `purge_customer_data`
  (approval + admin role + protected customers).
- `demo.py` runs the $10,000 refund story both ways — direct and
  behind the gateway — plus transfers, purge, and the audit log.
- 22 tests, all passing, run with `python -m unittest discover -s tests`.

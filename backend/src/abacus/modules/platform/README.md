# platform

Firm budgets and metering (SPEC-007). The gateway owns the data; this module authorises and serves it.

- `GET /v1/budget` (`budget.read`): the firm's monthly budget, the plan limit and this month's spend.
- `PUT /v1/budget` (`budget.manage`, fresh MFA): sets the budget, which is audited as `budget.updated`. The soft limit must be at most the hard limit, and the hard limit at most the plan limit.
- `GET /v1/metering?period=day|month` (`budget.read`): spend per engagement and agent.

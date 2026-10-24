# review

Zone: red. Pre-registered by F-03-T08 (ADR-140); empty until its first epic.

Will own (docs/plan/03-backend-architecture.md §2.2): Sign-offs, review notes, issues, decision cards and decisions, checkpoints, field value versions, the human-gates projection. Registration slots: reviewables, decision kinds, gate kinds, field owners.

## Content hash and staleness (P-04-T14; DEC-215)
- `review.api.content_hash(value)`: SHA-256 hex of the RFC 8785 canonical JSON (`hashing.py`, no dependency). Amounts are strings; a `Decimal`, NaN, an infinity or an integer past 2**53 - 1 is refused (`NotCanonical`). Owners hash through it (workpapers today).
- `ReviewableFacts` per target through `register_reviewable_facts` / `reviewable_facts` (fail closed).
- `stale_of(tenant, target_type, {target_id: current_hash})`: the newest sign-off per target and level whose hash differs, in one query. No sign-off row is ever updated.

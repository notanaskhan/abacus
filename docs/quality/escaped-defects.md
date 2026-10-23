# Escaped-defect log

A defect found after its code merged: by a back-fill suite, the nightly, staging, production or a partner. Each row names the zone, the path, the introducing task, the stage that found it, the severity, the sprint, and **the layer that should have caught it**, so the next suite or gate can be placed there (chapter 10 §10.14.2 "Flow"; Q-03 §3.2 B2; F-01 §3 escaped-defect form).

F-01-T15's issue form and delivery-health workflow are not built, and the solo edition works without GitHub issues (DEC-200), so this file is the log. The weekly quality report (`abacus_tools.quality.report`) counts its rows per sprint, by zone and by layer.

**Layers:** `unit`, `integration`, `contract`, `security`, `component`, `journey`, `review`, `spec` (the spec itself was wrong or silent). **Severity:** SEV1 to SEV4 (chapter 01 §1.6.5); a defect found by a test before any firm used the path is SEV4 unless it breaks tenancy, a wall or a human-only action (SEV3). **State:** `fixed` (the fix and its test merged together), `open` (an `xfail(strict=True)` test holds it, named in the task file).

| ID | Found | Sprint | Zone | Path | Introduced by | Found by | Severity | Should have been caught by | State | Fix or holding test |
|---|---|---|---|---|---|---|---|---|---|---|

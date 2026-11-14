# Contract request: rendered form pages and their field manifest (T17 → T-06)

F-07-T21 (TASK-7950). From F-07's T17 FormRendererLayout and TPL-17 to T-06 (entity depth), which
renders filed-form previews from the engine's values. F-07-T15's test-only faces show the shape.

## Screen states
TPL-17 a (page 1 with K-1s), b (Schedule K pages 4–5 traced), c (diagnostics), d (page 6 M-2 as
drafted), e (K-1 preview, DRAFT · pre-release), f (loading).

## Fields
Pages: `n`, `face`, `width_pt`, `height_pt`, the masked image (same-origin). Manifest field:
`id`, `label`, `value`, `page`, `rect_pt`, `match_id` (the server's), `diagnostic` (code). K-1
rows: `partner`, the four boxes, `status` (`draft_pre_release` until the engine's final),
`handoff` (the recipient return). Total = Schedule K tie state from the server.

## Seed figures
Ridgeline 2025 Form 1065: Schedule K 2 1,231,600 · 5 18,400 · 18a 6,200 · 19a 600,000; M-2 line 9
6,860,000 vs Schedule L line 21 6,866,200 (off 6,200); diagnostics 1 error (M-3 required) and 2
warnings.

# Contract request: the deadlines read model (T13 → T-08)

F-07-T21 (TASK-7950). From F-07's T13 MonthGrid and TPL-13 (firm deadlines, September 2026) to the
owner of the firm-deadline read model (T-08). The calendar reads today's `DueDateOut` per return;
the read model T-08 builds must serve, per day, the items below.

## Screen states
TPL-13 a (month, Sep 2026), a′ (day popover open), b (week), c (agenda), d (filtered to one
office), e (empty month), f (loading).

## Fields
Per item: `work_item_id`, `title`, `form`, `tax_year`, `due_on`, `kind` (`original` · `extended` ·
`installment` · `postponed`), `extension_form`, `assignee` `{user_id, name}`, `office_id`,
`state` (C2 `due_item`), `deep_link`. Per day: `count`, `overdue` (code's). Walls applied: a walled
item is absent and not counted.

## Seed figures
Brightwater Hale, Sep 2026: Sep 15 Ridgeline Property Partners, LP Form 1065 (extended, 7004 filed
Mar 12, 2026); Sep 15 Harborview Dental Properties, LP Form 1065 (8879-PE); Oct 15 the Feld and
Shah 1040s (extended).

// Planned link targets (chapter 04 §2.1 rule 4): a control that opens a screen whose manifest
// status is `planned` is hidden in production and drawn disabled, with its "Opens …" hint, in dev,
// fixture and gallery builds, so the artboards keep their designed affordances. A build folds the
// flags to constants, so production drops the planned controls entirely.

export const PLANNED_VISIBLE: boolean =
  import.meta.env.DEV ||
  import.meta.env.MODE === "test" ||
  import.meta.env.VITE_UI_GALLERY === "1" ||
  import.meta.env.VITE_FIXTURES === "1";

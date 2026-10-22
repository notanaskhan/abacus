// SHL-01's own words, verbatim from the handoff (spec.md and revision.md). The toolbar's labels
// are nav.ts's and the Toolbar kit's; the interim frames' words are shell/firm/copy.ts.

/** The T2 body under frame a: "a flex pane (header "Overview")" and a rail pane the same. */
export const PANE_TITLE = "Overview";

/** Frame g's strip labels (revision.md NEW STATES g), by screen ID. */
export const R2_LABELS = {
  "ENG-10": "ENG-10 Board",
  "HOME-05": "HOME-05 Today",
  "INS-01": "INS-01 Insights",
  "BND-04": "BND-04 Request tracker",
  "WB-12": "WB-12 Saved prompts",
  "KNW-06": "KNW-06 Engagement templates",
  "FSP-01": "FSP-01 Statements studio",
  "ATT-01": "ATT-01 Attest cockpit",
} as const;

/** The settings route of frame f (P-01 §5.3). */
export const SETTINGS_PATH = "/settings/general";

/** Frame e's widths: the 1400 width test and below 1280 (P-01 §5.3). */
export const WIDTHS = [1400, 1279] as const;

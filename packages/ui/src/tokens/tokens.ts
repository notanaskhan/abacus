// The typed mirror of the design tokens (SPEC-048 AC-1; ADR-155; design-foundations §1). The
// values live in theme.css (the @theme block Tailwind reads) and root.css (layout, z-index,
// scrims, motion); this file lists the same values for code that needs them as data (the
// gallery's /components/tokens page, charts, tests). apps/web/src/lint/tokens-mirror.test.ts
// proves the two agree exactly, in both directions, so a change to one fails until the other
// follows. Every change also adds a row to DECISIONS.md.

/** Colours by group. Each key is the utility name: `green-tint` is `bg-green-tint`, `--color-green-tint`. */
export const colors = {
  /** Surfaces, light to dark (9). */
  surfaces: {
    card: "#ffffff",
    "band-hd": "#fbfbfa",
    shell: "#f8f8f6",
    "nav-fill": "#f2f1ef",
    nested: "#efeeeb",
    "sel-bg": "#e8e6e0",
    chip: "#e1dfd9",
    // The plan calls this `surface`; that name still means the white SPEC-016 alias until the
    // legacy classes retire (F-05-T34), so the deep greige is `surface-deep` for now.
    "surface-deep": "#d7d5ce",
    presentation: "#e9e3dd",
  },
  /** Interaction fill for tonal buttons. */
  interaction: {
    "tonal-hover": "#d9d6cf",
  },
  /** Espresso ink on the AA alpha ladder (DEC-11): ink-2 .70 and ink-3 .66 meet 4.5:1 (7). */
  inks: {
    ink: "rgba(43, 31, 23, 0.95)",
    "ink-2": "rgba(43, 31, 23, 0.7)",
    "ink-3": "rgba(43, 31, 23, 0.66)",
    "ink-4": "rgba(43, 31, 23, 0.3)",
    hair: "rgba(43, 31, 23, 0.1)",
    rule: "rgba(43, 31, 23, 0.14)",
    stroke: "rgba(43, 31, 23, 0.22)",
  },
  /** Dark fills (the fifth, the CTA shadow, is `shadows.cta`). */
  dark: {
    espresso: "#2b1f17",
    "cta-hover": "#3b2a1f",
    "cta-press": "#22180f",
    "on-dark": "#fefefe",
  },
  /** Olive done, ochre in progress, brick issue; with their hover shades. */
  status: {
    green: "#5c6b2e",
    "green-ink": "#47521f",
    "green-tint": "#e6ebd8",
    "green-hover": "#525f29",
    "green-tint-hover": "#dce3ca",
    amber: "#ba8f45",
    "amber-ink": "#7c5718",
    "amber-tint": "#f6eedf",
    "amber-tint-hover": "#f0e4cf",
    "amber-line": "rgba(124, 87, 24, 0.22)",
    red: "#b13327",
    "red-ink": "#8e2418",
    "red-tint": "#f7e4e1",
    "red-tint-hover": "#f0d5d0",
    negative: "#b13327",
  },
  /** Document and client-service icon tiles only; never a text link. */
  clay: "#a45f3d",
  /** Source tracing only, never a status (8). `match-ink` is the AA text colour (DEC-11). */
  match: {
    "match-bg": "#ecd9f0",
    "match-bg-2": "#e4d1e9",
    "match-line": "#bf99c8",
    "match-ink": "#7e4590",
    "match-mark": "#dacfeb",
    "match-soft": "rgba(204, 189, 229, 0.62)",
    "match-i9": "#e9e3f2",
    "match-hover": "#f8f2f9",
  },
  /** Data visualisation: pastel fills p1-p4, deep lines and legend dots d1-d4 (8). */
  viz: {
    "viz-p1": "#d4c0b4",
    "viz-p2": "#c0c89f",
    "viz-p3": "#e1bf8d",
    "viz-p4": "#f3b5a8",
    "viz-d1": "#8a6c58",
    "viz-d2": "#687933",
    "viz-d3": "#936b1c",
    "viz-d4": "#b55545",
  },
  /** Rendered documents only (forms, PDFs, letters) and the highlighter swatches (10). */
  doc: {
    "doc-typed": "#6a98e8",
    "doc-ink": "#111111",
    "doc-black": "#000000",
    "doc-fill-dark": "#1a2f7a",
    "doc-check": "#8a97a8",
    "doc-zebra": "#fbfaf8",
    "hl-rose": "#e39a9a",
    "hl-apricot": "#e3b47e",
    "hl-sage": "#a9c08e",
    "hl-slate": "#9db2c9",
  },
  /** The SPEC-016 names still in use. The Atelier names (ground, muted, line, accent, info, ai)
   *  are retired and banned by eslint-design-rules.js (F-05-T34, DS-32). */
  aliases: {
    surface: "#ffffff",
    rail: "#f2f1ef",
    sunken: "#efeeeb",
    ok: "#47521f",
    "ok-soft": "#e6ebd8",
    warn: "#7c5718",
    "warn-soft": "#f6eedf",
    danger: "#8e2418",
    "danger-soft": "#f7e4e1",
  },
} as const;

const GEIST = '"Geist", "Inter Tight", -apple-system, "Helvetica Neue", Arial, sans-serif';

/** Font families. Geist at 400 and 500 only; the document faces load lazily (fonts-doc.css). */
export const fonts = {
  sans: GEIST,
  ui: GEIST,
  display: GEIST,
  mono: '"Geist Mono", ui-monospace, "SF Mono", Menlo, monospace',
  doc: '"Arimo", "Helvetica Neue", Arial, sans-serif',
  legal: '"Gelasio", Georgia, serif',
  statement: 'ui-monospace, "SF Mono", Menlo, Consolas, monospace',
} as const;

/** Legacy weight names, both 500 (Geist has no 600 or 700). `font-semibold` is banned by lint. */
export const fontWeights = {
  semibold: "500",
  bold: "500",
} as const;

export interface TextRole {
  /** `--text-<role>` */
  readonly size: string;
  /** `--text-<role>--line-height` */
  readonly lineHeight: string;
  /** `--text-<role>--letter-spacing`; absent where the role keeps the inherited tracking. */
  readonly letterSpacing?: string;
  /** `--text-<role>--font-weight`; absent where the element sets its own weight. */
  readonly weight?: string;
}

// The 22 roles of design-foundations §1.6 plus pill-card, kpi and the three button sizes. The
// six roles the F-05-T06 codemod maps Tailwind's text-xs/sm/base/lg/xl/2xl onto (meta, body, nav,
// pane, title, dashboard) carry only size and line height, at the values those classes had, so
// the codemod changes no pixel; their weight and tracking arrive with the primitives (F-05-T14).
// The body line height (1.45 against the plan's 1.2) is open in DECISIONS.md.
export const textRoles = {
  dashboard: { size: "20px", lineHeight: "1.2" },
  brand: { size: "16px", lineHeight: "1.2", letterSpacing: "-0.02em", weight: "500" },
  title: { size: "15px", lineHeight: "1.3" },
  pane: { size: "14.5px", lineHeight: "1.3" },
  tab: { size: "14px", lineHeight: "1.2", letterSpacing: "-0.005em" },
  section: { size: "13.5px", lineHeight: "1.2", letterSpacing: "-0.01em", weight: "500" },
  nav: { size: "13.5px", lineHeight: "1.45" },
  body: { size: "13px", lineHeight: "1.45" },
  chat: { size: "13.5px", lineHeight: "1.45", letterSpacing: "-0.005em" },
  dense: { size: "12.5px", lineHeight: "1.3", letterSpacing: "-0.005em" },
  para: { size: "12.5px", lineHeight: "1.55", letterSpacing: "-0.003em" },
  cell: { size: "12px", lineHeight: "1.2", letterSpacing: "-0.005em" },
  th: { size: "11.5px", lineHeight: "1.2", letterSpacing: "-0.003em" },
  meta: { size: "11.5px", lineHeight: "1.3" },
  count: { size: "11.5px", lineHeight: "1", weight: "500" },
  pill: { size: "12px", lineHeight: "1", letterSpacing: "-0.005em", weight: "500" },
  "pill-card": { size: "11.5px", lineHeight: "1", weight: "500" },
  "pill-sm": { size: "11px", lineHeight: "1", letterSpacing: "-0.003em", weight: "500" },
  micro: { size: "10.5px", lineHeight: "1", letterSpacing: "-0.002em", weight: "500" },
  "band-dark": { size: "12px", lineHeight: "1", letterSpacing: "0.04em", weight: "500" },
  "outline-hd": { size: "12px", lineHeight: "1", letterSpacing: "0.06em", weight: "500" },
  "group-row": { size: "10px", lineHeight: "1", letterSpacing: "0.07em", weight: "500" },
  "kpi-label": { size: "9.5px", lineHeight: "1", letterSpacing: "0.07em", weight: "500" },
  kpi: { size: "22px", lineHeight: "1.1" },
  "btn-lg": { size: "14px", lineHeight: "1.2" },
  btn: { size: "13.5px", lineHeight: "1.2" },
  "btn-sm": { size: "12.5px", lineHeight: "1.2" },
} as const satisfies Record<string, TextRole>;

/** The 13 radii. Controls are pills (DEC-124, which supersedes DEC-109 and DEC-123). */
export const radii = {
  pill: "999px",
  pane: "12px",
  nested: "10px",
  tile: "8px",
  "tile-lg": "9px",
  sheet: "6px",
  prop: "5px",
  value: "4px",
  dialog: "14px",
  menu: "15px",
  "menu-inner": "11px",
  window: "16px",
  phone: "28px",
} as const;

/** SPEC-016 radii for boxed inputs, selects and panels (about 60 call sites; F-05-T15 and the screen
 * rebuilds move them to nested, tile and pane). Not for buttons: Button is a pill (F-05-T14). */
export const legacyRadii = {
  control: "8px",
  panel: "12px",
} as const;

/** Elevation: every shadow begins with a 0.5px ink ring, which is the border. */
export const shadows = {
  e1: "0 0 0 0.5px rgba(43, 31, 23, 0.07), 0 1px 2px rgba(43, 31, 23, 0.05)",
  e2: "0 0 0 0.5px rgba(43, 31, 23, 0.06), 0 1px 2px rgba(43, 31, 23, 0.04), 0 4px 10px rgba(43, 31, 23, 0.05)",
  e3: "0 0 0 0.5px rgba(43, 31, 23, 0.05), 0 2px 4px rgba(43, 31, 23, 0.04), 0 14px 30px rgba(43, 31, 23, 0.1)",
  pop: "0 0 0 0.5px rgba(43, 31, 23, 0.1), 0 2px 6px rgba(43, 31, 23, 0.06), 0 18px 40px rgba(43, 31, 23, 0.18)",
  note: "0 0 0 0.5px rgba(43, 31, 23, 0.1), 0 14px 32px rgba(43, 31, 23, 0.2)",
  menu: "0 0 0 0.5px rgba(43, 31, 23, 0.1), 0 2px 6px rgba(43, 31, 23, 0.07), 0 22px 48px rgba(43, 31, 23, 0.2)",
  modal:
    "0 0 0 0.5px rgba(43, 31, 23, 0.1), 0 2px 6px rgba(43, 31, 23, 0.06), 0 26px 60px rgba(43, 31, 23, 0.22)",
  sheet:
    "0 0 0 0.5px rgba(43, 31, 23, 0.1), 0 4px 12px rgba(43, 31, 23, 0.1), 0 28px 70px rgba(43, 31, 23, 0.26)",
  ask: "0 0 0 0.5px rgba(43, 31, 23, 0.07), 0 2px 6px rgba(43, 31, 23, 0.06), 0 -2px 22px rgba(43, 31, 23, 0.06), 0 18px 40px rgba(43, 31, 23, 0.16)",
  fab: "0 0 0 0.5px rgba(43, 31, 23, 0.08), 0 2px 6px rgba(43, 31, 23, 0.1)",
  cta: "0 1px 2px rgba(43, 31, 23, 0.2)",
  lift: "0 1px 2px rgba(43, 31, 23, 0.18)",
  page: "0 0 0 0.5px rgba(43, 31, 23, 0.1), 0 2px 7px rgba(43, 31, 23, 0.16)",
} as const;

/** Inset rings: `hair` is e0, the recessed ring. */
export const insetShadows = {
  hair: "inset 0 0 0 0.5px rgba(43, 31, 23, 0.1)",
  sel: "inset 0 0 0 1px rgba(43, 31, 23, 0.22)",
  match: "inset 0 0 0 1px #bf99c8",
} as const;

export const eases = {
  out: "cubic-bezier(0.25, 1, 0.5, 1)",
  "in-out": "cubic-bezier(0.65, 0, 0.35, 1)",
  fly: "cubic-bezier(0.32, 0.72, 0.32, 1)",
} as const;

/** Durations and staggers (root.css). No bounces, no shimmer. */
export const motion = {
  "motion-color": "180ms ease",
  "motion-row": "200ms ease",
  "motion-press": "220ms cubic-bezier(0.25, 1, 0.5, 1)",
  "motion-reveal": "260ms cubic-bezier(0.25, 1, 0.5, 1)",
  "motion-match": "360ms ease",
  "motion-collapse": "340ms ease-out",
  "motion-spin": "820ms linear",
  "stagger-kpi": "45ms",
  "stagger-rows": "70ms",
  "stagger-docs": "135ms",
  "stagger-uploads": "130ms",
} as const;

/** Layout sizes (root.css), used as `h-(--toolbar-h)`. */
export const layout = {
  "app-w": "1400px",
  "toolbar-h": "46px",
  "subbar-h": "42px",
  "auditbar-h": "59px",
  "tabs-h": "50px",
  "tabs-h-compact": "44px",
  "tabs-h-workbench": "60px",
  "pane-hd-h": "46px",
  "bar-h": "44px",
  "rail-w": "330px",
  "rail-w-wide": "358px",
  "rail-w-list": "320px",
  "rail-w-portal": "336px",
  "rail-w-inbox": "392px",
  "tree-w": "214px",
  "wp-w": "536px",
  "ev-w": "490px",
  "queue-w": "262px",
  "queue-w-close": "310px",
  "queue-w-entity": "470px",
  "dock-w": "330px",
  "dock-w-doc": "360px",
  "nav-w-board": "280px",
  "drawer-w": "480px",
  "sheet-w": "500px",
  "dialog-w": "560px",
  "palette-w": "640px",
  "menu-w": "462px",
  "menu-w-sm": "240px",
  "gutter-pane": "10px",
  "edge-app": "12px",
} as const;

export const zIndex = {
  "z-pop": "30",
  "z-menu": "40",
  "z-drawer": "50",
  "z-modal": "60",
  "z-toast": "70",
} as const;

/** Scrims behind dialogs and the palette, the O3 agent sheet, and the O4 full sheet. */
export const scrims = {
  scrim: "rgba(43, 31, 23, 0.22)",
  "scrim-agent": "rgba(43, 31, 23, 0.28)",
  "scrim-sheet": "rgba(43, 31, 23, 0.3)",
} as const;

export const hairline = "0.5px solid var(--color-hair)";

/** Tailwind namespaces theme.css resets with `initial`, so only plan tokens compile. */
export const resets = ["color", "shadow"] as const;

/** The handoff's own ladder, applied under `<html data-contrast="reference">` (contrast.css) for parity runs only. */
export const referenceLadder = {
  "--color-ink-2": "rgba(43, 31, 23, 0.62)",
  "--color-ink-3": "rgba(43, 31, 23, 0.54)",
  "--color-match-ink": "#9253a2",
  "--focus-ring": "0 0 0 2px rgba(43, 31, 23, 0.28), 0 0 0 0.5px rgba(43, 31, 23, 0.22)",
} as const;

function prefixed(prefix: string, group: Readonly<Record<string, string>>): [string, string][] {
  return Object.entries(group).map(([name, value]) => [`--${prefix}${name}`, value]);
}

function textVariables(roles: Readonly<Record<string, TextRole>>): [string, string][] {
  return Object.entries(roles).flatMap(([name, role]): [string, string][] => [
    [`--text-${name}`, role.size],
    [`--text-${name}--line-height`, role.lineHeight],
    ...(role.letterSpacing === undefined
      ? []
      : [[`--text-${name}--letter-spacing`, role.letterSpacing] as [string, string]]),
    ...(role.weight === undefined
      ? []
      : [[`--text-${name}--font-weight`, role.weight] as [string, string]]),
  ]);
}

/** Every custom property in theme.css's `@theme static` block, by name. */
export const themeVariables: Readonly<Record<string, string>> = Object.fromEntries([
  ...prefixed("color-", colors.surfaces),
  ...prefixed("color-", colors.interaction),
  ...prefixed("color-", colors.inks),
  ...prefixed("color-", colors.dark),
  ...prefixed("color-", colors.status),
  ["--color-clay", colors.clay],
  ...prefixed("color-", colors.match),
  ...prefixed("color-", colors.viz),
  ...prefixed("color-", colors.doc),
  ...prefixed("color-", colors.aliases),
  ...prefixed("font-", fonts),
  ...prefixed("font-weight-", fontWeights),
  ...textVariables(textRoles),
  ...prefixed("radius-", radii),
  ...prefixed("radius-", legacyRadii),
  ...prefixed("shadow-", shadows),
  ...prefixed("inset-shadow-", insetShadows),
  ...prefixed("ease-", eases),
]);

/** Every custom property in root.css's `:root` block, by name. */
export const rootVariables: Readonly<Record<string, string>> = Object.fromEntries([
  ...prefixed("", motion),
  ...prefixed("", layout),
  ...prefixed("", zIndex),
  ...prefixed("", scrims),
  ["--hairline", hairline],
]);

import type { Tone } from "./components/surfaces";
import { HANDOFF_WORDS, RETIRED_CODES, STATUS_REGISTRY } from "./status.gen";

// The status vocabulary at run time (F-05-T12; C2, DEC-08, ADR-138). Every word, tone, disc and
// context label comes from docs/product/status-vocabulary.yaml through status.gen.ts. This file
// adds only what the YAML does not hold: how a registry variant or disc is drawn by the C-06
// kit. A new variant or disc in the YAML fails tsc here until this file says how it looks, and
// the same goes for an OpenAPI enum literal with no registry entry (apps/web status/enums.ts).

export interface StatusWord {
  label: string;
  tone: Tone;
}

// The legacy request, workpaper and result codes of TASK-101: still read by screens that have not
// moved to the registry. Their replacements are the `ui.*` entries in RETIRED_CODES.
export const STATUS = {
  // The plan's firm-side request words (S19 §3; TASK-105): asked, uploaded and waiting for the
  // team, screened and ready for a decision, or returned to the client. ("Received" means accepted
  // in the plan, so an upload is never called received.)
  // F-03-T15: request status v2 (chapter 09 §9.5.6): a firm-only draft, asked of the client,
  // uploaded and waiting for the team, returned, received (accepted), or not applicable.
  request: {
    draft: { label: "Draft", tone: "neutral" },
    requested: { label: "Requested", tone: "neutral" },
    uploaded: { label: "Uploaded", tone: "warning" },
    returned: { label: "Returned", tone: "danger" },
    received: { label: "Received", tone: "success" },
    not_applicable: { label: "Not applicable", tone: "neutral" },
  },
  // The client's words for their requests (the plan's POR-03; TASK-106): never the firm's states.
  clientRequest: {
    requested: { label: "To do", tone: "neutral" },
    uploaded: { label: "Done", tone: "success" },
    returned: { label: "Returned", tone: "danger" },
    received: { label: "Done", tone: "success" },
    not_applicable: { label: "Doesn't apply", tone: "neutral" },
  },
  engagement: {
    active: { label: "Active", tone: "success" },
    archived: { label: "Archived", tone: "neutral" },
  },
  workpaper: {
    not_started: { label: "Not started", tone: "neutral" },
    draft: { label: "Draft", tone: "warning" },
    ready: { label: "Prepared", tone: "warning" },
    reviewed: { label: "Reviewed", tone: "success" },
  },
  result: {
    supported: { label: "Supported", tone: "success" },
    exception: { label: "Exception", tone: "danger" },
    not_tested: { label: "Not tested", tone: "neutral" },
  },
  decision: {
    accept: { label: "Accepted", tone: "success" },
    reject: { label: "Sent back", tone: "warning" },
  },
} as const satisfies Record<string, Record<string, StatusWord>>;

export type StatusDomain = keyof typeof STATUS;

/** The word and tone for a state; an unknown state reads as itself, neutral. */
export function statusWord(domain: StatusDomain, value: string): StatusWord {
  const words: Record<string, StatusWord> = STATUS[domain];
  return words[value] ?? { label: value, tone: "neutral" };
}

// ---- The registry ----------------------------------------------------------------------------

type Registry = typeof STATUS_REGISTRY;
export type RegistryObject = keyof Registry;
export type RegistryCode<O extends RegistryObject> = keyof Registry[O] & string;

type AnyEntry = { [O in RegistryObject]: Registry[O][keyof Registry[O]] }[RegistryObject];
/** A variant the YAML uses (the blueprint's pill variants; `match` is never one). */
export type RegistryVariant = NonNullable<AnyEntry["variant"]>;
/** A disc or glyph name the YAML uses (blueprint 3.3.1). */
export type RegistryDisc = AnyEntry extends infer E
  ? E extends { disc: infer D extends string }
    ? D
    : never
  : never;
/** A named place that words or draws a code differently: `subbar_1040_1041`, `pill`, `tile`,
 * `subbar` and so on. */
export type RegistryContext = AnyEntry extends infer E
  ? | (E extends { contextLabels: infer L } ? keyof L & string : never)
    | (E extends { contextVariants: infer V } ? keyof V & string : never)
  : never;

/** The stored codes of an object: its codes that are not derived (never an `overdue`). */
export type StoredCode<O extends RegistryObject> = {
  [C in RegistryCode<O>]: Registry[O][C] extends { derived: true } ? never : C;
}[RegistryCode<O>];

/** `true` when every literal of an OpenAPI enum `E` has a registry entry under `O`, and every stored
 * code of `O` is in `E`; otherwise an object naming the difference, which no `true` accepts. */
export type EnumCovered<O extends RegistryObject, E extends string> = [
  Exclude<E, RegistryCode<O>>,
  Exclude<StoredCode<O>, E>,
] extends [never, never]
  ? true
  : {
      missingFromRegistry: Exclude<E, RegistryCode<O>>;
      missingFromEnum: Exclude<StoredCode<O>, E>;
    };

// ---- The kit's vocabulary (C-06) --------------------------------------------------------------

/** The pill variants (C-06). Purple `match` is source tracing and is never a status, so it is not
 * here. */
export type PillVariant =
  | "amber"
  | "green"
  | "green-tint"
  | "red"
  | "red-tint"
  | "neutral"
  | "muted"
  | "soon"
  | "outline"
  | "tag";
export type PillSize =
  | "state"
  | "card-state"
  | "sm"
  | "micro"
  | "status"
  | "outline"
  | "tally"
  | "tag"
  | "count"
  | "done"
  | "check"
  | "chip";
export type DiscState =
  "done" | "prepared" | "todo" | "half" | "run" | "warn" | "fail" | "off" | "wait";
/** The disc sizes: 13 in issue rows, 15 in rows and rails, 17 in task rows (C-06), and 16 for the
 * inbox's "new" and "waiting" rows, which the blueprint draws at 16. */
export type DiscSize = 13 | 15 | 16 | 17;
/** The sync chip's leading glyph. */
export type SyncGlyph = "refresh" | "spin" | "synced" | "out" | "pending" | "failed";
/** A sub-line beside a disc: ink-3, or amber ink. */
export type LineTone = "text" | "text-amber";

export const DISC_STATES: readonly DiscState[] = [
  "done",
  "prepared",
  "todo",
  "half",
  "run",
  "warn",
  "fail",
  "off",
  "wait",
];

/** The accessible name of each disc (C-06). */
export const DISC_LABEL: Record<DiscState, string> = {
  done: "Done",
  prepared: "Prepared",
  todo: "To do",
  half: "In progress",
  run: "Running",
  warn: "Warning",
  fail: "Failed",
  off: "Skipped",
  wait: "Waiting",
};

// A registry variant to a kit pill variant. `state` is the blueprint's name for the in-flight
// record state, which the kit draws as the amber tint. The `satisfies` is the exhaustiveness check.
const PILL_VARIANT = {
  state: "amber",
  amber: "amber",
  "green-tint": "green-tint",
  green: "green",
  "red-tint": "red-tint",
  red: "red",
  neutral: "neutral",
  muted: "muted",
  soon: "soon",
  outline: "outline",
  tag: "tag",
} as const satisfies Record<RegistryVariant, PillVariant>;

// The tone the older Badge and StatusPill take for a variant.
const VARIANT_TONE: Record<PillVariant, Tone> = {
  green: "success",
  "green-tint": "success",
  red: "danger",
  "red-tint": "danger",
  amber: "warning",
  neutral: "neutral",
  muted: "neutral",
  soon: "neutral",
  outline: "neutral",
  tag: "neutral",
};

interface DiscDrawing {
  state: DiscState;
  size?: DiscSize;
}

// A registry disc name to the kit's disc. `null` means C-06 draws nothing for it: the lock, the
// clock, the flags, the board's left bar, the statements cell treatments and the document check
// pill belong to the kit that owns the row, and the word carries the meaning (the kit allows no
// icon in a pill but the check and the spinner). The `satisfies` is the exhaustiveness check.
const DISC_DRAWING = {
  ring: { state: "todo" },
  ring_16: { state: "todo", size: 16 },
  ring_upload: { state: "todo" },
  half: { state: "half" },
  spinner: { state: "run" },
  atom_spinner: { state: "run" },
  check_olive: { state: "done" },
  check_olive_15: { state: "done", size: 15 },
  check_grey: { state: "prepared" },
  x_brick: { state: "fail" },
  x_grey: { state: "off" },
  x_ink4_15: { state: "off", size: 15 },
  triangle_amber: { state: "warn" },
  dot_amber: { state: "wait" },
  dot_gold_16: { state: "wait", size: 16 },
  refresh_amber: null,
  check_ink_micro: null,
  dot_olive: null,
  conic_dot_amber: null,
  clock: null,
  lock: null,
  flag: null,
  flag_amber: null,
  flag_brick: null,
  left_bar_brick: null,
  dotted_underline_amber: null,
  amber_tint_relink: null,
  // P-04-T02 (the review grammar's glyphs): drawn by the trust-kit overlays, not as a disc.
  atom: null,
  atom_olive: null,
  estimate_badge: null,
} as const satisfies Record<RegistryDisc, DiscDrawing | null>;

// The sync chip draws its leading glyph from the same names.
const SYNC_GLYPH: Partial<Record<RegistryDisc, SyncGlyph>> = {
  refresh_amber: "refresh",
  spinner: "spin",
  check_olive: "synced",
  triangle_amber: "out",
  dot_amber: "pending",
  x_brick: "failed",
};

// The pill size C-06 gives an object's states. Anything not listed is `state`; a tag variant is a
// `tag`, an outline `outline`, and a soon `sm`.
const OBJECT_SIZE: Partial<Record<RegistryObject, PillSize>> = {
  return_sync_chip: "chip",
  document: "sm",
  audit_engagement: "card-state",
  audit_section: "sm",
  close: "status",
  proposed_entry: "sm",
  workbench_session: "sm",
  issue: "sm",
  tie_out_tally: "tally",
};

function sizeFor(object: RegistryObject, variant: PillVariant | null): PillSize {
  const listed = OBJECT_SIZE[object];
  if (listed !== undefined) return listed;
  if (variant === "tag") return "tag";
  if (variant === "outline") return "outline";
  if (variant === "soon") return "sm";
  return "state";
}

// ---- Resolving a code -------------------------------------------------------------------------

interface RegistryEntry {
  readonly label: string;
  readonly variant: string | null;
  readonly terminal: boolean;
  readonly derived: boolean;
  readonly clientLabel?: string;
  readonly contextLabels?: Readonly<Record<string, string>>;
  readonly contextVariants?: Readonly<Record<string, string>>;
  readonly disc?: string;
  readonly textTone?: string;
  readonly emphasis?: string;
}

const REGISTRY: Readonly<Record<string, Readonly<Record<string, RegistryEntry>>>> =
  STATUS_REGISTRY;

export interface StatusOptions {
  /** Where the code is shown, when the registry words it differently there (`subbar_entity_returns`). */
  context?: RegistryContext;
  /** The client portal's wording, when the registry has one. */
  client?: boolean;
  /** Fills `{date}`, `{n}`, `{reason}` and the other placeholders in the label. */
  vars?: Readonly<Record<string, string | number>>;
}

export interface ResolvedStatus {
  object: RegistryObject;
  code: string;
  /** The word, with placeholders filled (never colour alone). */
  label: string;
  /** The pill variant, or `null` when the registry gives a disc and a line, or only a line. */
  variant: PillVariant | null;
  /** The kit's pill size for this object. */
  size: PillSize;
  /** The line beside a disc when there is no pill. */
  line: LineTone;
  /** The disc to draw before the word, or `null` (see DISC_DRAWING). */
  disc: { state: DiscState; size: DiscSize } | null;
  /** The sync chip's leading glyph. */
  glyph: SyncGlyph | null;
  /** The registry's own disc name, for the kit that draws what C-06 does not. */
  mark: RegistryDisc | null;
  /** A leading check: a finished state in the green solid pill (the label may carry its own). */
  check: boolean;
  /** The word is bold (a material weakness). */
  bold: boolean;
  /** The older tone, for Badge and the legacy StatusPill. */
  tone: Tone;
  terminal: boolean;
  /** Derived from a date or a count, never stored (`overdue`). */
  derived: boolean;
  /** Placeholders no `vars` filled; their text is dropped from the label. */
  unfilled: readonly string[];
  /** The code is not in the registry: the label is the code and the pill is neutral. */
  unknown: boolean;
}

function fill(
  template: string,
  vars: StatusOptions["vars"],
): { label: string; unfilled: string[] } {
  const unfilled: string[] = [];
  const label = template
    .replace(/\{(\w+)\}/g, (_m, key: string) => {
      const value = vars?.[key];
      if (value === undefined) {
        unfilled.push(key);
        return "";
      }
      return String(value);
    })
    .replace(/\s*·\s*$/, "")
    .replace(/\s+/g, " ")
    .trim();
  return { label, unfilled };
}

function isDiscName(name: string | undefined): name is RegistryDisc {
  return name !== undefined && name in DISC_DRAWING;
}

/** What a registry code looks like and says: `status("return", "preparing", { context:
 * "subbar_1040_1041" })` is "Draft". A code the registry does not hold (a value from a newer
 * server) reads as itself in a neutral pill; the types keep a literal from getting there. */
export function status<O extends RegistryObject>(
  object: O,
  code: RegistryCode<O>,
  options: StatusOptions = {},
): ResolvedStatus {
  const entry: RegistryEntry | undefined = REGISTRY[object]?.[code];
  if (entry === undefined) {
    return {
      object,
      code,
      label: code,
      variant: "neutral",
      size: "state",
      line: "text",
      disc: null,
      glyph: null,
      mark: null,
      check: false,
      bold: false,
      tone: "neutral",
      terminal: false,
      derived: false,
      unfilled: [],
      unknown: true,
    };
  }
  const { context, client, vars } = options;
  const contextLabel = context === undefined ? undefined : entry.contextLabels?.[context];
  const raw =
    contextLabel ??
    (client === true && entry.clientLabel !== undefined ? entry.clientLabel : entry.label);
  const { label, unfilled } = fill(raw, vars);
  const contextVariant = context === undefined ? undefined : entry.contextVariants?.[context];
  const registryVariant = (contextVariant ?? entry.variant) as RegistryVariant | null;
  const variant = registryVariant === null ? null : PILL_VARIANT[registryVariant];
  const mark = isDiscName(entry.disc) ? entry.disc : null;
  const drawing: DiscDrawing | null = mark === null ? null : DISC_DRAWING[mark];
  const glyph = object === "return_sync_chip" && mark !== null ? (SYNC_GLYPH[mark] ?? null) : null;
  return {
    object,
    code,
    label,
    variant,
    size: sizeFor(object, variant),
    line: entry.textTone === "amber" ? "text-amber" : "text",
    disc:
      glyph === null && drawing !== null
        ? { state: drawing.state, size: drawing.size ?? 15 }
        : null,
    glyph,
    mark,
    check: variant === "green" && object !== "tie_out_tally" && !label.includes("✓"),
    bold: entry.emphasis === "bold",
    tone: variant === null ? "neutral" : VARIANT_TONE[variant],
    terminal: entry.terminal,
    derived: entry.derived,
    unfilled,
    unknown: false,
  };
}

// The tone each registry variant had before the kit (the legacy Badge): state reads as info.
const LEGACY_TONE: Record<string, Tone> = {
  green: "success",
  "green-tint": "success",
  red: "danger",
  "red-tint": "danger",
  amber: "warning",
  state: "info",
};

/** The registry's word and tone for a code; `client` uses the portal wording when there is one.
 * Placeholders ({date}, {reason}) are filled from `fill`, or dropped with their separator.
 * Kept for callers that predate `status()`; new code reads `status()`. */
export function registryWord(
  object: RegistryObject,
  code: string,
  options: { client?: boolean; fill?: Record<string, string> } = {},
): StatusWord {
  const entry: RegistryEntry | undefined = REGISTRY[object]?.[code];
  if (entry === undefined) return { label: code, tone: "neutral" };
  const raw =
    options.client === true && entry.clientLabel !== undefined ? entry.clientLabel : entry.label;
  const { label } = fill(raw, options.fill);
  return { label, tone: LEGACY_TONE[entry.variant ?? ""] ?? "neutral" };
}

// ---- The handoff's 144 words ------------------------------------------------------------------

type Handoff = typeof HANDOFF_WORDS;
export type HandoffObject = keyof Handoff;

export interface RetiredWord {
  /** The registry code that replaces it (`engagement.prospect`), or `null` when the concept is not
   * a status any more: a count line, a kind line or an event. */
  replacement: string | null;
  /** Why it has no registry code of its own. */
  reason: string;
}

interface HandoffEntry {
  readonly object?: string;
  readonly code?: string;
  readonly retired?: true;
  readonly reason?: string;
  readonly replacement?: string | null;
}

const HANDOFF: Readonly<Record<string, Readonly<Record<string, HandoffEntry>>>> = HANDOFF_WORDS;

/** Every word of the handoff's lib/status.js that has no registry code, by "Object.Word". The other
 * words are mapped: `handoffStatus` resolves them. Together they are all 144. */
export const RETIRED: Readonly<Record<string, RetiredWord>> = Object.fromEntries(
  Object.entries(HANDOFF).flatMap(([object, words]) =>
    Object.entries(words).flatMap(([word, entry]) =>
      entry.retired === true
        ? [
            [
              `${object}.${word}`,
              { replacement: entry.replacement ?? null, reason: entry.reason ?? "" },
            ] as const,
          ]
        : [],
    ),
  ),
);

/** The handoff's objects and words, in the order of lib/status.js. */
export const HANDOFF_OBJECTS: Readonly<Record<string, readonly string[]>> = Object.fromEntries(
  Object.entries(HANDOFF).map(([object, words]) => [object, Object.keys(words)]),
);

/** A status.js word, resolved: the registry code it became, or why it was retired. */
export function handoffStatus(
  object: string,
  word: string,
  options: StatusOptions = {},
): { mapped: ResolvedStatus } | { retired: RetiredWord } | null {
  const entry = HANDOFF[object]?.[word];
  if (entry === undefined) return null;
  if (entry.retired === true) {
    return { retired: { replacement: entry.replacement ?? null, reason: entry.reason ?? "" } };
  }
  const target = entry.object as RegistryObject;
  return { mapped: status(target, entry.code as RegistryCode<typeof target>, options) };
}

/** The codes and words retired from the repo and the design sources, with their replacements. */
export { RETIRED_CODES };

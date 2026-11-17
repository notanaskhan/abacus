// The copy registry (F-05-T32; plan 04 §8.1 and lint L2). Designed words live in copy modules:
// `apps/web/src/screens/<ID>/copy.ts` through `defineCopy("<ID>", {...} as const)`, verbatim from
// the handoff, and shared product words in `copy/common.ts`. `defineCopy` returns the copy as given
// (casing is never transformed, G-D06) and records it with the rules its namespace keeps;
// `lintCopy` is L2, run over every copy module by copy-registry.test.ts.

/** A copy tree: strings, functions that build a string from data, and nested trees. */
export interface CopyTree {
  readonly [key: string]: string | ((...args: never[]) => string) | CopyTree | readonly string[];
}

export type CopySurface = "firm" | "portal";

export interface CopyRules {
  /** Portal namespaces never say the product's name (DEC-01, ADR-133). Inferred from the id:
   * `POR-*` and `*.portal` are portal; everything else is firm. */
  surface: CopySurface;
  /** Key paths in the agent's voice (a dotted path, or a prefix ending in "."): no "!". Any key
   * whose name starts with "agent" is agent voice too. */
  agent: readonly string[];
  /** Key paths of labels that open a dialog: they end in "…" (U+2026), never "...". */
  opensDialog: readonly string[];
  /** Close keys allowed to say "task" (plan 04 L2); every other key says "to-do". */
  task: readonly string[];
}

export interface CopyNamespace {
  id: string;
  rules: CopyRules;
  copy: CopyTree;
}

const REGISTRY = new Map<string, CopyNamespace>();

export function surfaceOf(id: string): CopySurface {
  return id.startsWith("POR-") || id.endsWith(".portal") ? "portal" : "firm";
}

/** Keys outside the close screens that name the close run's tasks (glossary "Close task (UI)"),
 * never a to-do, for copy modules that cannot register their own rules. One entry per key, each
 * verbatim from its handoff (DEC-1274). */
const CLOSE_TASK_KEYS: Readonly<Record<string, readonly string[]>> = {
  // ADM-04 gate row 2: "Draft a return, workpaper or close task" (handoff spec.md, gates table).
  "ADM-04": ["COPY.rows.2"],
  // CLS-03 b: "Re-run affected tasks" after an incorporation (SPEC-655, C-01 T19 acceptance).
  "CLS-03": ["COPY.rerunAffected"],
};

function rulesFor(id: string, rules: Partial<CopyRules> | undefined): CopyRules {
  return {
    surface: rules?.surface ?? surfaceOf(id),
    agent: rules?.agent ?? [],
    opensDialog: rules?.opensDialog ?? [],
    task: rules?.task ?? CLOSE_TASK_KEYS[id] ?? [],
  };
}

/** Register a namespace's copy and return it unchanged, typed exactly as written. */
export function defineCopy<const T extends CopyTree>(
  id: string,
  copy: T,
  rules?: Partial<CopyRules>,
): T {
  REGISTRY.set(id, { id, rules: rulesFor(id, rules), copy });
  return copy;
}

/** Every namespace `defineCopy` has seen, by id. */
export function registeredCopy(): readonly CopyNamespace[] {
  return [...REGISTRY.values()].sort((a, b) => a.id.localeCompare(b.id));
}

/** A namespace for a copy module that does not call `defineCopy` (its rules from its id). */
export function namespaceOf(
  id: string,
  copy: CopyTree,
  rules?: Partial<CopyRules>,
): CopyNamespace {
  return { id, rules: rulesFor(id, rules), copy };
}

// ---- L2 -------------------------------------------------------------------------------------------

export interface CopyFinding {
  namespace: string;
  key: string;
  rule:
    | "emoji"
    | "agent-bang"
    | "three-dots"
    | "opener-ellipsis"
    | "portal-name"
    | "task"
    | "todo"
    | "export-for-tax"
    | "qip-roof"
    | "partnership-word"
    | "statement-dollar";
  text: string;
}

const EMOJI = /\p{Extended_Pictographic}/u;
const PRODUCT = /accrued/i;
const TASK = /\btasks?\b/i;
// The noun is "To-do", hyphenated; "Todo", "ToDo" and "todos" are never written. ("To do" as a
// status group, "Nothing to do", is a verb phrase and stays.)
const TODO = /\btodos?\b/i;
const ELLIPSIS = "…";
// T-06-T04 (SPEC-702 AC-26; DEC-5512): the entity-depth bans. "Export for Tax" is never a label
// (the hand-off is "Hand off to tax…"); TXP-03 never calls the Elm Street roof "QIP"; an 1120 or
// 990 frame never speaks partnership words; statement grammar carries no "$".
const EXPORT_FOR_TAX = /\bexport for tax\b/i;
const QIP = /\bQIP\b/;
const PARTNERSHIP = /\b(?:partners?|partnership|K-1s?|capital accounts?|§754|§752)\b/i;
/** Key prefixes of the 1120 and 990 frames (TXP-13 b, b2, c, c2, c3, d). */
const CORPORATE_FRAMES = ["form1120.", "form990.", "provision.", "functionalExpenses."];
/** Key prefixes in statement grammar: figures without "$" (T-06 screens). */
const STATEMENT_KEYS = ["statement.", "statements."];
const ENTITY_DEPTH = new Set([
  "TXP-03",
  "TXP-04",
  "TXP-08",
  "TXP-09",
  "TXP-13",
  "TAX-11",
  "AUD-38",
]);

/** The texts a copy value can produce. A function is called with placeholder data, so the words
 * around the data are checked; a function that needs real data is checked by its screen's tests. */
function textsOf(value: unknown): string[] {
  if (typeof value === "string") return [value];
  if (Array.isArray(value)) return value.filter((v): v is string => typeof v === "string");
  if (typeof value === "function") {
    const fn = value as (...args: unknown[]) => unknown;
    for (const arg of ["1", 1]) {
      try {
        const out = fn(...Array<unknown>(Math.max(fn.length, 1)).fill(arg));
        if (typeof out === "string") return [out];
      } catch {
        // Try the next placeholder.
      }
    }
  }
  return [];
}

function matches(path: string, keys: readonly string[]): boolean {
  return keys.some((k) => (k.endsWith(".") ? path.startsWith(k) : path === k));
}

function isAgentKey(path: string, rules: CopyRules): boolean {
  return matches(path, rules.agent) || path.split(".").some((segment) => /^agent/i.test(segment));
}

function walk(tree: unknown, prefix: string, visit: (path: string, value: unknown) => void): void {
  if (tree === null || typeof tree !== "object" || Array.isArray(tree)) {
    visit(prefix, tree);
    return;
  }
  for (const [key, value] of Object.entries(tree)) {
    walk(value, prefix === "" ? key : `${prefix}.${key}`, visit);
  }
}

/** L2 over one namespace: every finding, or none. */
export function lintCopy(ns: CopyNamespace): CopyFinding[] {
  const found: CopyFinding[] = [];
  const add = (key: string, rule: CopyFinding["rule"], text: string): void => {
    found.push({ namespace: ns.id, key, rule, text });
  };
  walk(ns.copy, "", (key, value) => {
    for (const text of textsOf(value)) {
      if (EMOJI.test(text)) add(key, "emoji", text);
      if (text.includes("...")) add(key, "three-dots", text);
      if (isAgentKey(key, ns.rules) && text.includes("!")) add(key, "agent-bang", text);
      if (matches(key, ns.rules.opensDialog) && !text.endsWith(ELLIPSIS)) {
        add(key, "opener-ellipsis", text);
      }
      if (ns.rules.surface === "portal" && PRODUCT.test(text)) add(key, "portal-name", text);
      if (TASK.test(text) && !matches(key, ns.rules.task)) add(key, "task", text);
      if (TODO.test(text)) add(key, "todo", text);
      if (EXPORT_FOR_TAX.test(text)) add(key, "export-for-tax", text);
      if (ns.id === "TXP-03" && QIP.test(text)) add(key, "qip-roof", text);
      if (ns.id === "TXP-13" && matches(key, CORPORATE_FRAMES) && PARTNERSHIP.test(text)) {
        add(key, "partnership-word", text);
      }
      if (ENTITY_DEPTH.has(ns.id) && matches(key, STATEMENT_KEYS) && text.includes("$")) {
        add(key, "statement-dollar", text);
      }
    }
  });
  return found;
}

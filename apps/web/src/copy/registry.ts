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

function rulesFor(id: string, rules: Partial<CopyRules> | undefined): CopyRules {
  return {
    surface: rules?.surface ?? surfaceOf(id),
    agent: rules?.agent ?? [],
    opensDialog: rules?.opensDialog ?? [],
    task: rules?.task ?? [],
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
    "emoji" | "agent-bang" | "three-dots" | "opener-ellipsis" | "portal-name" | "task" | "todo";
  text: string;
}

const EMOJI = /\p{Extended_Pictographic}/u;
const PRODUCT = /accrued/i;
const TASK = /\btasks?\b/i;
// The noun is "To-do", hyphenated; "Todo", "ToDo" and "todos" are never written. ("To do" as a
// status group, "Nothing to do", is a verb phrase and stays.)
const TODO = /\btodos?\b/i;
const ELLIPSIS = "…";

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
    }
  });
  return found;
}

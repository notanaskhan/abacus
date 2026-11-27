// F-08-T28 (DEC-6026): what a transaction may never do to the paper, enforced in ProseMirror
// (filterTransaction), so no key, paste, drop or IME composition gets around it:
// - change or remove a read-only statement table or a linked value (their figures are the
//   consumer's, ADR-050), so a linked number cannot be typed over, deleted or pasted into;
// - touch a section another person is editing (one editor at a time, ADR P-59).
import type { Node as PmNode } from "@tiptap/pm/model";
import { Plugin, PluginKey, type Transaction } from "@tiptap/pm/state";

// F-08-T29: a linked value is guarded the same way: its figure changes only through an intent.
export const PROTECTED_NODES = ["statementTable", "linkedValue"] as const;

function protectedIn(doc: PmNode): string[] {
  const found: string[] = [];
  doc.descendants((node) => {
    if ((PROTECTED_NODES as readonly string[]).includes(node.type.name)) {
      found.push(`${node.type.name}:${JSON.stringify(node.attrs)}`);
    }
    return true;
  });
  return found;
}

function sectionRanges(doc: PmNode, locked: ReadonlySet<string>): [number, number][] {
  const ranges: [number, number][] = [];
  doc.forEach((node, offset) => {
    if (node.type.name === "section" && locked.has(String(node.attrs["key"]))) {
      ranges.push([offset, offset + node.nodeSize]);
    }
  });
  return ranges;
}

export function touchesLocked(tr: Transaction, locked: ReadonlySet<string>): boolean {
  if (locked.size === 0) return false;
  const ranges = sectionRanges(tr.before, locked);
  return tr.steps.some((step, i) => {
    // The step's ranges are in the document as the steps before it left it.
    const before = tr.mapping.slice(0, i);
    const here = ranges.map(([a, b]) => [before.map(a, 1), before.map(b, -1)] as const);
    let hit = false;
    step.getMap().forEach((oldStart, oldEnd) => {
      if (here.some(([a, b]) => oldStart < b && oldEnd > a)) hit = true;
    });
    return hit;
  });
}

export const protectKey = new PluginKey("abacus-editor-protect");

/** The guard plugin; `locked()` reads the sections other people are editing now. */
export function protectPlugin(locked: () => ReadonlySet<string>): Plugin {
  return new Plugin({
    key: protectKey,
    filterTransaction(tr) {
      if (!tr.docChanged) return true;
      if (tr.getMeta("abacus-consumer-set-content") === true) return true;
      const before = protectedIn(tr.before);
      const after = protectedIn(tr.doc);
      if (before.length !== after.length || before.some((p, i) => p !== after[i])) return false;
      return !touchesLocked(tr, locked());
    },
  });
}

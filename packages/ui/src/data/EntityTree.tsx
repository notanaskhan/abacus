import { type JSX, type KeyboardEvent, useRef, useState } from "react";
import { cn } from "../cn";

// C-35 EntityTree (A-09-T08; AUD-32 c; A-09 §5.6): a group structure as a treegrid, three tiers at
// most. Every row carries `aria-level`; arrows move focus; Alt+Arrow Up/Down move an entity with
// its subtree among its siblings, Alt+Arrow Right indents it under the sibling above, Alt+Arrow
// Left outdents it. Drag handles are drawn for pointer users, but drag is never the only path:
// every move is a keyboard command, announced in a polite live region. The tree computes nothing
// about balances; it reports the new order and levels through `onChange`, and the server saves
// the structure (`PUT …/structure`). Ownership is a fixed 100% fact (X-06), shown, never edited.

export interface EntityNode {
  id: string;
  name: string;
  /** 1 to `maxLevel`. */
  level: number;
  /** "100% · Chicago". */
  meta?: string;
}

export interface EntityTreeProps {
  label: string;
  nodes: readonly EntityNode[];
  /** Called with the whole list after a move; omit for a read-only tree. */
  onChange?: (nodes: EntityNode[]) => void;
  maxLevel?: number;
  className?: string;
}

/** The index just past `i`'s subtree (its descendants follow it with deeper levels). */
function subtreeEnd(nodes: readonly EntityNode[], i: number): number {
  const level = nodes[i]?.level ?? 0;
  let j = i + 1;
  while (j < nodes.length && (nodes[j]?.level ?? 0) > level) j += 1;
  return j;
}

function previousSibling(nodes: readonly EntityNode[], i: number): number {
  const level = nodes[i]?.level ?? 0;
  for (let j = i - 1; j >= 0; j -= 1) {
    const at = nodes[j]?.level ?? 0;
    if (at === level) return j;
    if (at < level) return -1;
  }
  return -1;
}

/** Move `i`'s subtree up or down past its neighbouring sibling's subtree. */
export function moveEntity(
  nodes: readonly EntityNode[],
  i: number,
  dir: -1 | 1,
): EntityNode[] | null {
  const end = subtreeEnd(nodes, i);
  const block = nodes.slice(i, end);
  if (dir === -1) {
    const prev = previousSibling(nodes, i);
    if (prev < 0) return null;
    return [...nodes.slice(0, prev), ...block, ...nodes.slice(prev, i), ...nodes.slice(end)];
  }
  const next = end;
  if (next >= nodes.length || nodes[next]?.level !== nodes[i]?.level) return null;
  const nextEnd = subtreeEnd(nodes, next);
  return [...nodes.slice(0, i), ...nodes.slice(next, nextEnd), ...block, ...nodes.slice(nextEnd)];
}

/** Indent (+1) or outdent (−1) `i` with its subtree; null when the move is not allowed. */
export function shiftEntity(
  nodes: readonly EntityNode[],
  i: number,
  delta: -1 | 1,
  maxLevel = 3,
): EntityNode[] | null {
  const node = nodes[i];
  if (node === undefined) return null;
  const end = subtreeEnd(nodes, i);
  const deepest = Math.max(...nodes.slice(i, end).map((n) => n.level));
  if (delta === 1 && (previousSibling(nodes, i) < 0 || deepest + 1 > maxLevel)) return null;
  if (delta === -1 && node.level <= 2) return null; // one root: only the parent sits at level 1
  return nodes.map((n, k) => (k >= i && k < end ? { ...n, level: n.level + delta } : n));
}

export function EntityTree({
  label,
  nodes,
  onChange,
  maxLevel = 3,
  className,
}: EntityTreeProps): JSX.Element {
  const [focus, setFocus] = useState(0);
  const [said, setSaid] = useState("");
  const rows = useRef<(HTMLDivElement | null)[]>([]);
  const go = (i: number): void => {
    const next = Math.max(0, Math.min(nodes.length - 1, i));
    setFocus(next);
    rows.current[next]?.focus();
  };
  const apply = (next: EntityNode[] | null, id: string, what: string): void => {
    if (next === null || onChange === undefined) {
      setSaid(`Cannot ${what}`);
      return;
    }
    onChange(next);
    const at = next.findIndex((n) => n.id === id);
    const moved = next[at];
    setSaid(
      moved === undefined
        ? ""
        : `${moved.name}: level ${String(moved.level)}, position ${String(at + 1)} of ${String(next.length)}`,
    );
    setFocus(at);
    queueMicrotask(() => rows.current[at]?.focus());
  };
  const onKey = (event: KeyboardEvent<HTMLDivElement>, i: number): void => {
    const node = nodes[i];
    if (node === undefined) return;
    if (event.altKey) {
      const plan: Record<string, [EntityNode[] | null, string] | undefined> = {
        ArrowUp: [moveEntity(nodes, i, -1), "move up"],
        ArrowDown: [moveEntity(nodes, i, 1), "move down"],
        ArrowRight: [shiftEntity(nodes, i, 1, maxLevel), "move in"],
        ArrowLeft: [shiftEntity(nodes, i, -1, maxLevel), "move out"],
      };
      const step = plan[event.key];
      if (step !== undefined) {
        event.preventDefault();
        apply(step[0], node.id, step[1]);
      }
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      go(i + 1);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      go(i - 1);
    } else if (event.key === "Home") {
      event.preventDefault();
      go(0);
    } else if (event.key === "End") {
      event.preventDefault();
      go(nodes.length - 1);
    }
  };
  return (
    <div className={cn("flex flex-col", className)}>
      <div
        role="treegrid"
        aria-label={label}
        aria-readonly={onChange === undefined}
        className="flex flex-col"
      >
        {nodes.map((node, i) => (
          <div
            key={node.id}
            role="row"
            aria-level={node.level}
            tabIndex={i === focus ? 0 : -1}
            ref={(el) => {
              rows.current[i] = el;
            }}
            onKeyDown={(e) => {
              onKey(e, i);
            }}
            onFocus={() => {
              setFocus(i);
            }}
            data-entity={node.id}
            className="flex h-[38px] items-center gap-2 border-b-[0.5px] border-hair pr-3 outline-none focus-visible:bg-sel-bg"
            style={{ paddingLeft: `${String(12 + (node.level - 1) * 16)}px` }}
          >
            {onChange !== undefined && (
              <span aria-hidden className="w-3 text-ink-4">
                ⋮⋮
              </span>
            )}
            <span role="gridcell" className="flex-1 truncate text-dense font-medium">
              {node.name}
            </span>
            {node.meta !== undefined && (
              <span role="gridcell" className="text-meta text-ink-3">
                {node.meta}
              </span>
            )}
          </div>
        ))}
      </div>
      <p aria-live="polite" className="sr-only" data-entity-tree-status>
        {said}
      </p>
    </div>
  );
}

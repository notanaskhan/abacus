import { type JSX, type KeyboardEvent, useId, useMemo, useState } from "react";
import { cn } from "../cn";
import { Icon } from "../icons";
import { HIT } from "../components/hit-area";
import { MoneyCell } from "./cells";

// AccountTree (C-01 spec 02; F-05-T43): a chart of accounts in the ledger grammar. Sections
// ("Assets", "Liabilities") hold 37px account rows indented 12, 30 and 48 by level, with a 13px
// chevron column (empty for leaves), the account number in ink-3 before the name, and the balance
// on the right in the money format (negatives red). No connector lines. Balances are the server's;
// a parent's balance is sent, never added up here (ADR-050).
//
// Keyboard (a `tree`, one focus stop with `aria-activedescendant`): ↑ ↓ move over visible rows,
// Home and End jump, → opens a closed parent or moves to its first child, ← closes an open parent
// or moves to its parent, Enter opens. Clicking the chevron toggles; clicking the row selects.

export interface Account {
  id: string;
  /** "1010": drawn before the name in ink-3. */
  num?: string;
  name: string;
  /** A decimal string from the server. */
  balance: string;
  /** Default open; `false` starts the parent collapsed. */
  open?: boolean;
  children?: readonly Account[];
}

export interface AccountSection {
  title: string;
  accounts: readonly Account[];
}

export interface AccountTreeProps {
  /** The tree's accessible name. */
  label: string;
  sections: readonly AccountSection[];
  selected?: string | null;
  onSelect?: (account: Account) => void;
  onOpen?: (account: Account) => void;
  className?: string;
}

interface Visible {
  account: Account;
  level: number;
  parent: string | null;
}

const INDENT = [12, 30, 48] as const;

function initialOpen(sections: readonly AccountSection[]): Set<string> {
  const open = new Set<string>();
  const walk = (list: readonly Account[]): void => {
    for (const a of list) {
      if ((a.children?.length ?? 0) > 0 && a.open !== false) open.add(a.id);
      walk(a.children ?? []);
    }
  };
  for (const s of sections) walk(s.accounts);
  return open;
}

function visibleRows(accounts: readonly Account[], open: ReadonlySet<string>): Visible[] {
  const out: Visible[] = [];
  const walk = (list: readonly Account[], level: number, parent: string | null): void => {
    for (const account of list) {
      out.push({ account, level, parent });
      if (open.has(account.id)) walk(account.children ?? [], level + 1, account.id);
    }
  };
  walk(accounts, 0, null);
  return out;
}

export function AccountTree({
  label,
  sections,
  selected,
  onSelect,
  onOpen,
  className,
}: AccountTreeProps): JSX.Element {
  const base = useId();
  const [open, setOpen] = useState<ReadonlySet<string>>(() => initialOpen(sections));
  const [own, setOwn] = useState<string | null>(null);
  const current = selected === undefined ? own : selected;
  const bySection = useMemo(
    () => sections.map((s) => ({ section: s, rows: visibleRows(s.accounts, open) })),
    [sections, open],
  );
  const flat = bySection.flatMap((s) => s.rows);
  const idOf = (id: string): string => `${base}-${id}`;

  const select = (account: Account): void => {
    if (selected === undefined) setOwn(account.id);
    onSelect?.(account);
  };
  const toggle = (id: string): void => {
    setOpen((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>): void => {
    if (flat.length === 0) return;
    const at = flat.findIndex((r) => r.account.id === current);
    const row = flat[at];
    const go = (index: number): void => {
      event.preventDefault();
      const target = flat[Math.max(0, Math.min(flat.length - 1, index))];
      if (target !== undefined) select(target.account);
    };
    switch (event.key) {
      case "ArrowDown":
        go(at < 0 ? 0 : at + 1);
        break;
      case "ArrowUp":
        go(at < 0 ? 0 : at - 1);
        break;
      case "Home":
        go(0);
        break;
      case "End":
        go(flat.length - 1);
        break;
      case "ArrowRight": {
        if (row === undefined || (row.account.children?.length ?? 0) === 0) return;
        event.preventDefault();
        if (open.has(row.account.id)) go(at + 1);
        else toggle(row.account.id);
        break;
      }
      case "ArrowLeft": {
        if (row === undefined) return;
        event.preventDefault();
        if (open.has(row.account.id)) toggle(row.account.id);
        else if (row.parent !== null) {
          const parent = flat.findIndex((r) => r.account.id === row.parent);
          go(parent);
        }
        break;
      }
      case "Enter":
        if (row !== undefined) {
          event.preventDefault();
          onOpen?.(row.account);
        }
        break;
      default:
    }
  };

  return (
    <div
      role="tree"
      aria-label={label}
      tabIndex={0}
      aria-activedescendant={current === null ? undefined : idOf(current)}
      onKeyDown={onKeyDown}
      className={cn(
        "flex flex-col text-section font-normal tracking-[-0.005em] focus-visible:outline-offset-[-2px]",
        className,
      )}
    >
      {bySection.map(({ section, rows }, s) => (
        <div key={section.title} role="group" aria-label={section.title}>
          <div
            aria-hidden="true"
            className={cn(
              "flex h-[31px] items-center bg-band-hd px-[12px] text-body text-ink-2",
              s > 0 && "hairline-t",
            )}
          >
            {section.title}
          </div>
          {rows.map(({ account, level }) => {
            const parent = (account.children?.length ?? 0) > 0;
            const isOpen = open.has(account.id);
            const isSelected = account.id === current;
            return (
              <div
                key={account.id}
                id={idOf(account.id)}
                role="treeitem"
                aria-level={level + 1}
                aria-selected={isSelected}
                {...(parent ? { "aria-expanded": isOpen } : {})}
                onClick={() => {
                  select(account);
                }}
                onDoubleClick={() => onOpen?.(account)}
                style={{ paddingLeft: INDENT[Math.min(level, INDENT.length - 1)] }}
                className={cn(
                  "flex h-[37px] cursor-default items-center gap-[8px] pr-[12px] hairline-t transition-colors duration-200",
                  isSelected ? "bg-sel-bg font-medium" : "hover:bg-nested",
                )}
              >
                <span className="flex size-[13px] flex-none items-center justify-center">
                  {parent && (
                    <button
                      type="button"
                      tabIndex={-1}
                      aria-label={isOpen ? `Collapse ${account.name}` : `Expand ${account.name}`}
                      onClick={(event) => {
                        event.stopPropagation();
                        toggle(account.id);
                      }}
                      className={cn(
                        "relative flex size-[13px] items-center justify-center text-ink-3",
                        HIT.issue,
                      )}
                    >
                      <Icon
                        name="chevron-right"
                        size={13}
                        className={cn(
                          "transition-transform duration-[180ms]",
                          isOpen && "rotate-90",
                        )}
                      />
                    </button>
                  )}
                </span>
                <span className="min-w-0 flex-1 truncate">
                  {account.num !== undefined && (
                    <span className="mr-[8px] text-ink-3 tabular-nums">{account.num}</span>
                  )}
                  {account.name}
                </span>
                <MoneyCell value={account.balance} format="money" className="tracking-[-0.01em]" />
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}

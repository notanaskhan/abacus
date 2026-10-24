import {
  type HTMLAttributes,
  type JSX,
  type ReactNode,
  type TdHTMLAttributes,
  useSyncExternalStore,
} from "react";
import { cn } from "../cn";
import { MATCH_CELL, MATCH_ROW, useMatch, useMatchStore } from "../tracing/match";
import type { MatchId } from "../tracing/types";

// The E4 tracing cells (F-05-T50, F-05-T52): a row that lights while one of its matches is the
// scope's active one, and a cell that is the exact cell a citation lights. Every grammar shares
// them, so a cell's match id always comes from its typed locator (INV-2).

/** A row that lights (the match fill) while one of its cells' matches is the scope's active one.
 * Without ids it is a plain row and never subscribes. */
export function MatchRow({
  ids,
  className,
  children,
  ...props
}: HTMLAttributes<HTMLTableRowElement> & {
  ids: readonly MatchId[];
  children: ReactNode;
}): JSX.Element {
  const store = useMatchStore();
  const lit = useSyncExternalStore(
    store.subscribe,
    () => ids.length > 0 && ids.includes(store.get().id as MatchId),
    () => false,
  );
  return (
    <tr
      {...props}
      {...(lit ? { "data-lit": "" } : {})}
      className={cn(className, ids.length > 0 && MATCH_ROW)}
    >
      {children}
    </tr>
  );
}

/** A cell; with a match id it is the exact cell a citation lights (C-07: the deeper fill, the
 * 1.5px inset line, match ink at 500), and hovering it lights it after the row intent. */
export function MatchCell({
  match,
  ...props
}: TdHTMLAttributes<HTMLTableCellElement> & { match: MatchId | undefined }): JSX.Element {
  return match === undefined ? <td {...props} /> : <LitCell match={match} {...props} />;
}

function LitCell({
  match,
  className,
  ...props
}: TdHTMLAttributes<HTMLTableCellElement> & { match: MatchId }): JSX.Element {
  const { bind } = useMatch(match, "cell");
  return <td {...props} {...bind} data-match-kind="cell" className={cn(className, MATCH_CELL)} />;
}

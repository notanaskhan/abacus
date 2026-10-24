// SHL-07's footer chips (P-03-T11; AC-11): "Citations (n)" lists the section's citations and
// "Procedures (n)" its distinct methodology steps, each in a 420-wide list popover read from
// `GET /v1/citations?host_ref=…&section_id=…`. Choosing a citation pins its popover on the cell
// that carries its match; titles and locations are the server's (INV-2).

import type { CitationV2Out } from "@abacus/api-client";
import { listCitationsOptions } from "@abacus/api-client/query";
import { Icon, Popover, useMatchStore } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { toCiteViews } from "./CitationPopoverContainer";
import { COPY } from "./copy";

export const LIST_WIDTH = 420;

const CHIP =
  "inline-flex h-[28px] items-center gap-[7px] rounded-pill bg-card px-[12px] text-cell font-medium text-ink shadow-e1 hover:bg-nested data-[state=open]:bg-nested";
const ROW =
  "flex min-h-[36px] w-full items-center gap-[8px] rounded-tile px-[10px] text-left text-body text-ink hover:bg-nav-fill";

/** The distinct methodology steps among a section's citations, by match. */
export function proceduresOf(items: readonly CitationV2Out[]): CitationV2Out[] {
  const seen = new Set<string>();
  return items.filter((c) => {
    if (c.kind !== "methodology_step") return false;
    const key = c.match_id ?? c.id;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export interface CitationListProps {
  kind: "citations" | "procedures";
  hostRef: string;
  sectionId: string;
}

export function CitationList({ kind, hostRef, sectionId }: CitationListProps): JSX.Element {
  const store = useMatchStore();
  const [open, setOpen] = useState(false);
  const { data } = useQuery(
    listCitationsOptions({ query: { host_ref: hostRef, section_id: sectionId } }),
  );
  const all = data?.items ?? [];
  const rows = kind === "citations" ? all : proceduresOf(all);
  const views = toCiteViews(rows);
  const label = kind === "citations" ? COPY.chips.citationsLabel : COPY.chips.proceduresLabel;
  return (
    <Popover
      label={label}
      width={LIST_WIDTH}
      align="start"
      open={open}
      onOpenChange={setOpen}
      trigger={
        <button
          type="button"
          data-cite="chip"
          data-state={open ? "open" : "closed"}
          className={CHIP}
        >
          <Icon name={kind === "citations" ? "file-text" : "notebook-text"} size={12} />
          {kind === "citations"
            ? COPY.chips.citations(rows.length)
            : COPY.chips.procedures(rows.length)}
        </button>
      }
    >
      <ul data-cite="list" aria-label={label} className="flex flex-col gap-[1px] p-[4px]">
        {views.map((view, index) => (
          <li key={view.out.id}>
            <button
              type="button"
              className={ROW}
              onClick={() => {
                setOpen(false);
                const origin = view.match === null ? null : store.anchorFor(view.match, null);
                store.togglePin(view.match, origin, { list: views, index });
              }}
            >
              <span className="min-w-0 flex-1 truncate">{view.title}</span>
              <span className="max-w-[46%] flex-none truncate text-cell text-ink-3">
                {view.out.verified ? view.loc : COPY.popover.unverified}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </Popover>
  );
}

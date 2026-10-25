// The SHL-08 linked-figure card (P-03-T14; AC3.2; spec frame A, StatRow grammar): the verified
// citations from the opening record into this version (`GET /v1/citations?host_ref=…&
// source_version_id=…`), one row each, label left in ink-2 and `value_text` right. A row and its
// page region carry one match, so hovering either lights both in the same purple. The title row
// steps the anchor's stack ("Source 1 of 3 ‹ ›").

import type { CitationV2Out } from "@abacus/api-client";
import { listCitationsOptions } from "@abacus/api-client/query";
import { Icon, type ViewerRegion, cn, contractMatchId, useMatch } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import type { JSX } from "react";
import { COPY } from "./copy";

/** The rows a card shows: verified citations with a figure, in the order they sit on the page. */
export function figureRows(
  items: readonly CitationV2Out[],
  regions: readonly ViewerRegion[],
): CitationV2Out[] {
  const top = (c: CitationV2Out): number => {
    const r = regions.find((g) => g.match === c.match_id);
    return r === undefined ? Number.MAX_SAFE_INTEGER : r.page * 10_000 + (r.rects[0]?.[1] ?? 0);
  };
  return items
    .filter(
      (c) => c.verified && c.state === "valid" && c.value_text !== null && c.match_id !== null,
    )
    .sort((a, b) => top(a) - top(b) || a.n - b.n);
}

function Row({ citation }: { citation: CitationV2Out }): JSX.Element {
  const match = contractMatchId({ match_id: citation.match_id ?? "", kind: citation.kind });
  const { bind, pin } = useMatch(match, "row");
  return (
    <li>
      <button
        type="button"
        {...bind}
        data-match-kind="row"
        onClick={(e) => {
          pin(e.currentTarget);
        }}
        className={cn(
          "flex h-[36px] w-full items-center justify-between gap-[12px] rounded-nested px-[12px] text-left text-body",
          "transition-[background-color,box-shadow,color] duration-[360ms] ease-out",
          "data-[lit]:bg-match-bg data-[lit]:inset-ring-1 data-[lit]:inset-ring-match-line",
          "group",
        )}
      >
        <span className="min-w-0 truncate text-ink-2 group-data-[lit]:font-medium group-data-[lit]:text-ink">
          {citation.title}
        </span>
        <span className="shrink-0 font-medium tabular-nums">
          {figureValue(citation.value_text ?? "")}
        </span>
      </button>
    </li>
  );
}

function StepButton({
  icon,
  label,
  disabled,
  onClick,
}: {
  icon: "chevron-left" | "chevron-right";
  label: string;
  disabled: boolean;
  onClick: () => void;
}): JSX.Element {
  return (
    <button
      type="button"
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      className="inline-flex size-[22px] items-center justify-center rounded-pill text-ink-2 hover:bg-nested disabled:text-ink-4 disabled:hover:bg-transparent"
    >
      <Icon name={icon} size={13} />
    </button>
  );
}

/** "307,900" reads "$307,900" on a money figure; a word ("IL / CO / NY") stays as it is. */
export function figureValue(value: string): string {
  return /^[\d,]+(\.\d+)?$/.test(value) ? `$${value}` : value;
}

export interface LinkedFiguresProps {
  /** `<anchor type>:<anchor id>`: the record the viewer was opened from. */
  hostRef: string;
  versionId: string;
  figure: string | null;
  regions: readonly ViewerRegion[];
  /** The anchor's stack, and where the viewer stands in it. */
  stack: { index: number; total: number; onStep: (to: number) => void } | null;
}

export function LinkedFigures({
  hostRef,
  versionId,
  figure,
  regions,
  stack,
}: LinkedFiguresProps): JSX.Element | null {
  const { data } = useQuery(
    listCitationsOptions({ query: { host_ref: hostRef, source_version_id: versionId } }),
  );
  const rows = figureRows(data?.items ?? [], regions);
  if (rows.length === 0 && stack === null) return null;
  return (
    <section
      data-linked-figures=""
      aria-label={COPY.figure(figure)}
      className="m-[10px] mb-0 flex-none overflow-hidden rounded-pane bg-card shadow-e1"
    >
      <header className="flex h-[34px] items-center justify-between bg-band-hd px-[12px]">
        <h3 className="truncate text-dense font-medium">{COPY.figure(figure)}</h3>
        {stack !== null && stack.total > 1 && (
          <span className="flex items-center gap-[2px] text-meta text-ink-2">
            <span aria-live="polite" className="pr-[4px]">
              {COPY.source(stack.index + 1, stack.total)}
            </span>
            <StepButton
              icon="chevron-left"
              label={COPY.previousSource}
              disabled={stack.index <= 0}
              onClick={() => {
                stack.onStep(stack.index - 1);
              }}
            />
            <StepButton
              icon="chevron-right"
              label={COPY.nextSource}
              disabled={stack.index >= stack.total - 1}
              onClick={() => {
                stack.onStep(stack.index + 1);
              }}
            />
          </span>
        )}
      </header>
      {rows.length > 0 && (
        <ul className="flex flex-col p-[4px]">
          {rows.map((c) => (
            <Row key={c.id} citation={c} />
          ))}
        </ul>
      )}
    </section>
  );
}

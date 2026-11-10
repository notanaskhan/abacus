import {
  EvidenceTriad,
  Picker,
  SourceViewer,
  Toast,
  type TriadDoc,
  type TriadGroup,
  type TriadPreset,
  TriadFooter,
  TriadTree,
  type ViewerFile,
  amount,
  cn,
  createMatchStore,
  type CitationPayload,
  Icon,
  IconButton,
  type MatchId,
  matchIdOf,
  useMatch,
  useReducedMotion,
} from "@abacus/ui";
import { FORM_PAGE_PNG } from "@abacus/ui/specimens";
import { type JSX, useEffect, useState } from "react";
import {
  CARDS,
  COPY,
  DEMO_MS,
  type LeadRow,
  MISMATCH_3B,
  REGIONS,
  TREE,
  type Tax04Frame,
} from "./copy";

// TAX-04 · Return › Review, Prepare preset (T-04-T13; handoff TAX-04) in fixture mode on T3
// EvidenceTriad (214 · 571 · 571): the review tree (document variant, no action pills), the
// SourceViewer with its region layer, and the Form 1040 leadsheet cards, lit through one
// MatchScope (purple only through MatchProvider). A source box and the line it feeds share one
// match id, the region's C4 locator (INV-2), so they light together; the demo's order lights box
// 1a, 1b, then lines 3b and 3a (700/1000/1950/2250 ms) and the poster holds all four; reduced
// motion lights them at once. Approve
// Document is a person's act (TriadFooter's HumanAction; an agent draws none) and moves Review
// 36 to 35 with the ink "✓ 1"; a mismatch disables it with "Resolve 1 mismatch to approve".
//
//   a  unapproved, Review 36        b  approved: ✓ 1, Review 35, Unapprove Document, toast
//   c  mismatch: 3b reads 14,280    d  the draft Ridgeline K-1: box 5 lit with its row, 18A not
//   e  loading pages

export type { Tax04Frame } from "./copy";

const PERSON = { kind: "human", name: "Kevin Osei" } as const;
const NO_MATCH = "" as MatchId;

type RegionKey = keyof typeof REGIONS;

function matchOf(key: RegionKey): MatchId {
  const r = REGIONS[key];
  return matchIdOf({
    kind: "document_text",
    evidence_version_id: `feld-${r.doc}-2025`,
    page: 1,
    bbox: r.bbox,
  });
}

const PAGES = [1, 2].map((n) => ({
  n,
  width_pt: 612,
  height_pt: 792,
  rotation: 0 as const,
  src: FORM_PAGE_PNG,
}));

function fileOf(doc: string, label: string): ViewerFile {
  if (doc === "halvard") {
    return {
      name: COPY.halvardFile,
      pages: PAGES,
      regions: (["div1a", "div1b", "int1"] as const).map((k) => ({
        match: matchOf(k),
        page: 1,
        rects: [REGIONS[k].bbox],
        label: REGIONS[k].label,
        ...(k === "div1a" ? { linkedFigure: COPY.linked3b } : {}),
        ...(k === "div1b" ? { linkedFigure: COPY.linked3a } : {}),
      })),
    };
  }
  if (doc === "k1") {
    return {
      name: COPY.k1File,
      pages: PAGES,
      regions: (["k1box5", "k1box18a"] as const).map((k) => ({
        match: matchOf(k),
        page: 1,
        rects: [REGIONS[k].bbox],
        label: REGIONS[k].label,
      })),
    };
  }
  return { name: label, pages: PAGES.slice(0, 1), regions: [] };
}

const whole = (v: string): string => `$${amount(v, "whole").text}`;

function LeadLine({ row, mismatch }: { row: LeadRow; mismatch: boolean }): JSX.Element {
  const id = row.ties === undefined ? NO_MATCH : matchOf(row.ties);
  const { lit, bind, pin } = useMatch(id, "row");
  const off = mismatch && row.id === "3b";
  return (
    <li
      {...(row.ties === undefined ? {} : bind)}
      data-lead-row={row.id}
      data-lit={lit ? "true" : undefined}
      onClick={(event) => {
        if (row.ties !== undefined) pin(event.currentTarget);
      }}
      className={cn(
        "flex h-[34px] items-center gap-[8px] px-[14px] text-body hairline-t transition-[background-color] duration-[360ms]",
        lit && "bg-match-bg",
      )}
    >
      <span className={cn("min-w-0 flex-1 truncate", row.line === true && "font-medium")}>
        {row.label}
      </span>
      {row.flag === true && (
        <Icon name="flag" size={12} aria-label="Flagged" className="flex-none text-amber" />
      )}
      {off && <Icon name="flag" size={12} aria-label="Mismatch" className="flex-none text-red" />}
      <span
        className={cn(
          "tabular-nums",
          row.line === true && "font-medium",
          row.value === "0" && row.flag === true && "text-ink-4",
          off && "font-medium text-red-ink",
        )}
      >
        {whole(off ? MISMATCH_3B : row.value)}
      </span>
    </li>
  );
}

function Leadsheet({ mismatch }: { mismatch: boolean }): JSX.Element {
  return (
    <div data-leadsheet="form-1040" className="flex flex-col gap-[8px] bg-shell p-[8px]">
      {CARDS.map((card) => (
        <section
          key={card.id}
          aria-label={card.title}
          className="overflow-hidden rounded-pane bg-card shadow-e1"
        >
          <h3 className="flex h-[34px] items-center px-[14px] text-body font-medium">
            {card.title}
          </h3>
          <ul>
            {card.rows.map((row) => (
              <LeadLine key={row.id} row={row} mismatch={mismatch} />
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

function treeOf(approved: ReadonlySet<string>): readonly TriadGroup[] {
  return TREE.map((g) => ({
    id: g.id,
    label: g.label,
    subs: g.subs.map((s) => ({
      id: s.id,
      label: s.label,
      docs: s.docs.map(([id, label]): TriadDoc => ({
        id,
        label,
        ...(approved.has(id) ? { approved: true } : {}),
        ...(id === "k1" ? { flags: 1, flagsNote: COPY.issueNote } : {}),
      })),
    })),
  }));
}

export interface Tax04Props {
  frame?: Tax04Frame;
  onIssue?: (documentId: string) => void;
  onTab?: (tab: string) => void;
  onPreset?: (preset: TriadPreset) => void;
}

export function TAX04({ frame = "a", onIssue, onTab, onPreset }: Tax04Props): JSX.Element {
  const reduced = useReducedMotion();
  const [selected, setSelected] = useState(frame === "d" ? "k1" : "halvard");
  const [approved, setApproved] = useState<ReadonlySet<string>>(
    () => new Set(frame === "b" ? ["halvard"] : []),
  );
  const [toast, setToast] = useState<string | null>(frame === "b" ? COPY.approvedToast : null);
  const [store] = useState(() => {
    const s = createMatchStore<CitationPayload>();
    if (frame === "d") s.togglePin(matchOf("k1box5"), null);
    return s;
  });
  // The demo's order (handoff MOTION; T-04-T13, DEC-3171): box 1a at 700 ms, box 1b at 1000,
  // line 3b at 1950 and line 3a at 2250; the poster at 3600 holds all four. Each is its own
  // element kind of one match (a box and the line it feeds share an id), kept lit by the store
  // until a person moves the match; reduced motion lights all four at once. Frames d and e open
  // still.
  useEffect(() => {
    if (frame !== "a" && frame !== "c" && frame !== "b") return undefined;
    const steps: readonly [number, RegionKey, "region" | "row"][] = [
      [DEMO_MS.first, "div1a", "region"],
      [DEMO_MS.second, "div1b", "region"],
      [DEMO_MS.third, "div1a", "row"],
      [DEMO_MS.fourth, "div1b", "row"],
    ];
    if (reduced) {
      for (const [, key, kind] of steps) store.keepLit(matchOf(key), kind);
      return undefined;
    }
    const timers = steps.map(([at, key, kind]) =>
      setTimeout(() => {
        store.keepLit(matchOf(key), kind);
      }, at),
    );
    return () => {
      for (const t of timers) clearTimeout(t);
    };
  }, [frame, reduced, store]);

  const mismatch = frame === "c" && selected === "halvard";
  const isApproved = approved.has(selected);
  const review = COPY.tabs.review - approved.size;
  const label =
    TREE.flatMap((g) => g.subs.flatMap((s) => s.docs)).find(([id]) => id === selected)?.[1] ?? "";
  const file = fileOf(selected, label);

  return (
    <div data-screen="TAX-04" data-frame={frame} className="relative flex min-h-0 flex-1 flex-col">
      <EvidenceTriad
        embedded
        store={store}
        toolbar={{ nav: [], active: "Tax Returns", firm: "" }}
        record={{
          title: COPY.record.title,
          context: COPY.record.context,
          state: COPY.record.state,
          sync: "synced",
          syncDate: COPY.record.syncDate,
        }}
        tabs={{
          label: COPY.tabs.label,
          active: "Review",
          options: [
            "Overview",
            { label: "Intake", count: COPY.tabs.intake },
            { label: "Review", count: review },
            { label: "Issues", count: COPY.tabs.issues, bad: true },
            "Activity",
          ],
          ...(onTab === undefined ? {} : { onChange: onTab }),
        }}
        preset="prepare"
        {...(onPreset === undefined ? {} : { onPreset })}
        tree={{
          title: COPY.tree,
          body: (
            <TriadTree
              groups={treeOf(approved)}
              selected={selected}
              onSelect={(d) => {
                setSelected(d.id);
              }}
            />
          ),
          footer: (stacked) => (
            <div className="flex w-full flex-col gap-[6px]">
              <TriadFooter
                actor={PERSON}
                approved={isApproved}
                disabled={mismatch}
                stacked={stacked}
                onApprove={() => {
                  setApproved((a) => new Set([...a, selected]));
                  if (selected === "halvard") setToast(COPY.approvedToast);
                }}
                onUnapprove={() => {
                  setApproved((a) => new Set([...a].filter((d) => d !== selected)));
                  setToast(null);
                }}
                onIssue={() => onIssue?.(selected)}
              />
              {mismatch && (
                <p data-mismatch-helper className="text-meta text-ink-3">
                  {COPY.mismatchHelper}
                </p>
              )}
            </div>
          ),
        }}
        viewer={
          <SourceViewer
            file={file}
            loading={frame === "e"}
            menu={COPY.menu.map((l) => ({ label: l, onSelect: () => undefined }))}
          />
        }
        sheet={{
          tabs: [
            { label: "Worksheets", icon: "panels-top-left" },
            { label: "Leadsheets", icon: "layers" },
            { label: "2-Year Comparison", icon: "chart-column" },
          ],
          active: "Leadsheets",
          bar: (
            <>
              <IconButton icon="list-filter" label="Filter lines" variant="white" />
              <span className="flex flex-1 justify-center">
                <Picker
                  label="Leadsheet"
                  variant="white"
                  options={[{ value: "1040", label: COPY.picker }]}
                  value="1040"
                  onChange={() => undefined}
                />
              </span>
              <IconButton icon="refresh-cw" label="Refresh from the tax engine" variant="white" />
              <IconButton icon="upload" label="Export" variant="white" />
            </>
          ),
          children: <Leadsheet mismatch={mismatch} />,
        }}
      />
      {toast !== null && (
        <div className="pointer-events-none absolute bottom-[24px] left-1/2 -translate-x-1/2">
          <Toast kind="success" text={toast} still />
        </div>
      )}
    </div>
  );
}

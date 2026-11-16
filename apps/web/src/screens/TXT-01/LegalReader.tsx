import type { InstrumentClauseOut, ViewerTextPageOut } from "@abacus/api-client";
import { Icon, Menu } from "@abacus/ui";
import { type JSX, useEffect, useMemo, useRef, useState } from "react";
import { type ReaderBlock, readerBlocks } from "../../domain/tax";
import { COPY } from "./copy";

// TXT-01's legal reader (T-07-T15; OQ-2): SourceViewer's LegalReader mode as the screen needs it —
// the instrument reflowed from its masked text projection into clause pages (article headings on
// hairlines, lettered clauses with a hanging indent), the lavender passage highlight, the page
// stepper, zoom, rotate and search, and the header menu (Download · Open in Files). A chip's hover
// lights its passage and scrolls to it (smooth; instant under reduced motion, AC-2.2); a passage's
// click lists the determinations that cite it (a3). No clause text is stored server-side: the
// words are the projection's, masked where a scan found an identifier.

export interface LegalReaderProps {
  fileName: string;
  pageCount: number;
  pages: readonly ViewerTextPageOut[];
  clauses: readonly InstrumentClauseOut[];
  /** The clause label lit (a chip's hover, the selected row's clauses). */
  lit: readonly string[];
  /** The determinations citing each clause label, for a passage's click (a3). */
  citing: Readonly<Record<string, readonly string[]>>;
  onDownload?: () => void;
  onOpenInFiles?: () => void;
}

const reducedMotion = (): boolean =>
  typeof window !== "undefined" &&
  typeof window.matchMedia === "function" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/** The clause a page opens inside: the latest-starting clause that began on an earlier page. */
function carryOf(clauses: readonly InstrumentClauseOut[], page: number): string | null {
  const open = clauses.filter((c) => c.page_from < page && c.page_to >= page);
  return open.length === 0 ? null : (open[open.length - 1]?.label ?? null);
}

const belongs = (label: string | null, lit: readonly string[]): boolean =>
  label !== null && lit.some((l) => label === l || label.startsWith(`${l}(`));

function Block({
  block,
  lit,
  query,
  onPick,
}: {
  block: ReaderBlock;
  lit: readonly string[];
  query: string;
  onPick: (label: string) => void;
}): JSX.Element {
  const on = belongs(block.label, lit);
  const marked = (text: string): JSX.Element | string => {
    const q = query.trim();
    if (q.length < 3) return text;
    const at = text.toLowerCase().indexOf(q.toLowerCase());
    if (at < 0) return text;
    return (
      <>
        {text.slice(0, at)}
        <mark className="rounded-[2px] bg-amber-tint text-ink">
          {text.slice(at, at + q.length)}
        </mark>
        {text.slice(at + q.length)}
      </>
    );
  };
  if (block.kind === "article") {
    return (
      <h4
        data-clause={block.label}
        className="mt-[14px] border-t-[0.5px] border-hair pt-[9px] pl-[9px] text-[12.5px] font-medium tracking-[.02em] uppercase"
      >
        {marked(block.heading)}
      </h4>
    );
  }
  const label = block.label;
  const body = (
    <span
      data-lit={on ? "true" : "false"}
      className={on ? "rounded-[5px] bg-match-soft pt-[3px] pb-[4px] pl-[3px]" : undefined}
    >
      {marked(block.text)}
    </span>
  );
  return (
    <p
      data-clause={label ?? undefined}
      className={
        block.kind === "clause"
          ? "relative mt-[6px] pl-[43px] -indent-[23px] leading-[1.55]"
          : "mt-[6px] leading-[1.55]"
      }
    >
      {block.kind === "clause" && (
        <span className="inline-block w-[23px] indent-0">{block.letter}</span>
      )}
      {label === null ? (
        body
      ) : (
        <button
          type="button"
          className="text-left"
          onClick={() => {
            onPick(label);
          }}
        >
          {body}
        </button>
      )}
    </p>
  );
}

export function LegalReader({
  fileName,
  pageCount,
  pages,
  clauses,
  lit,
  citing,
  onDownload,
  onOpenInFiles,
}: LegalReaderProps): JSX.Element {
  const readable = useMemo(() => pages.filter((p) => !p.unread), [pages]);
  const [index, setIndex] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [rotation, setRotation] = useState(0);
  const [searching, setSearching] = useState(false);
  const [query, setQuery] = useState("");
  const [picked, setPicked] = useState<string | null>(null);
  const well = useRef<HTMLDivElement>(null);
  const page = readable[index];
  const blocks = useMemo(
    () => (page === undefined ? [] : readerBlocks(page.text, carryOf(clauses, page.page))),
    [page, clauses],
  );

  // AC-2.2: a lit clause is scrolled into view at once (smooth, or instant under reduced motion).
  const first = lit[0];
  useEffect(() => {
    if (first === undefined || well.current === null) return;
    const target = well.current.querySelector<HTMLElement>(`[data-clause="${CSS.escape(first)}"]`);
    if (target === null) {
      const at = readable.findIndex((p) =>
        readerBlocks(p.text, carryOf(clauses, p.page)).some((b) => b.label === first),
      );
      if (at >= 0 && at !== index) setIndex(at);
      return;
    }
    if (typeof target.scrollIntoView === "function") {
      target.scrollIntoView({ behavior: reducedMotion() ? "auto" : "smooth", block: "center" });
    }
  }, [first, readable, clauses, index]);

  const capsule = "inline-flex items-center gap-[2px] rounded-pill bg-card p-[3px] shadow-e1";
  const tool =
    "inline-flex h-[26px] min-w-[26px] items-center justify-center rounded-pill px-[6px] text-dense hover:bg-nested";
  return (
    <section className="flex min-h-0 flex-1 flex-col" data-legal-reader>
      <header className="relative flex h-[46px] shrink-0 items-center justify-center gap-[6px]">
        <span className="text-[14.5px] font-medium">{fileName}</span>
        <Menu
          label={COPY.reader.menu}
          trigger={
            <button type="button" aria-label={COPY.reader.menu} className="text-ink-3">
              <Icon name="ellipsis" size={14} />
            </button>
          }
          sections={[
            [
              {
                label: COPY.reader.download,
                onSelect: () => onDownload?.(),
                disabled: onDownload === undefined,
              },
              {
                label: COPY.reader.openInFiles,
                onSelect: () => onOpenInFiles?.(),
                disabled: onOpenInFiles === undefined,
              },
            ],
          ]}
        />
      </header>
      <div className="flex h-[44px] shrink-0 items-center justify-center gap-[7px]" role="toolbar">
        <span className={capsule}>
          <button
            type="button"
            aria-label={COPY.reader.zoomOut}
            className={tool}
            onClick={() => {
              setZoom((z) => Math.max(0.6, z - 0.1));
            }}
          >
            <Icon name="zoom-out" size={14} />
          </button>
          <button
            type="button"
            className={tool}
            onClick={() => {
              setZoom(1);
            }}
          >
            {COPY.reader.fit}
          </button>
          <button
            type="button"
            aria-label={COPY.reader.zoomIn}
            className={tool}
            onClick={() => {
              setZoom((z) => Math.min(1.6, z + 0.1));
            }}
          >
            <Icon name="zoom-in" size={14} />
          </button>
          <button
            type="button"
            aria-label={COPY.reader.rotate}
            className={tool}
            onClick={() => {
              setRotation((r) => (r + 90) % 360);
            }}
          >
            <Icon name="rotate-cw" size={14} />
          </button>
        </span>
        <span className={capsule}>
          <button
            type="button"
            aria-label={COPY.reader.previous}
            className={tool}
            disabled={index === 0}
            onClick={() => {
              setIndex((i) => Math.max(0, i - 1));
            }}
          >
            <Icon name="chevron-up" size={14} />
          </button>
          <span className="px-[4px] text-dense tabular-nums" data-page-stepper>
            {String(page?.page ?? 1)} <span className="text-ink-2">/ {String(pageCount)}</span>
          </span>
          <button
            type="button"
            aria-label={COPY.reader.next}
            className={tool}
            disabled={index >= readable.length - 1}
            onClick={() => {
              setIndex((i) => Math.min(readable.length - 1, i + 1));
            }}
          >
            <Icon name="chevron-down" size={14} />
          </button>
        </span>
        <span className={capsule}>
          <span
            role="img"
            aria-label={COPY.reader.highlight}
            className="m-[5px] inline-block size-[15px] rounded-full bg-match-soft"
          />
        </span>
        <span className={capsule}>
          <button
            type="button"
            aria-label={COPY.reader.search}
            aria-pressed={searching}
            className={tool}
            onClick={() => {
              setSearching((s) => !s);
            }}
          >
            <Icon name="search" size={14} />
          </button>
          {searching && (
            <input
              aria-label={COPY.reader.searchPlaceholder}
              placeholder={COPY.reader.searchPlaceholder}
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
              }}
              className="h-[26px] w-[180px] rounded-pill bg-nested px-[10px] text-dense"
            />
          )}
        </span>
      </div>
      <div ref={well} className="min-h-0 flex-1 overflow-auto bg-shell py-[16px]">
        <article
          className="mx-auto w-[760px] max-w-full bg-card px-[52px] py-[40px] text-[12px] text-ink shadow-e1"
          style={{
            transform: `scale(${String(zoom)}) rotate(${String(rotation)}deg)`,
            transformOrigin: "top center",
          }}
          aria-label={fileName}
        >
          {blocks.length === 0 ? (
            <p className="text-ink-3">{COPY.reader.noText}</p>
          ) : (
            blocks.map((b, i) => (
              <div key={`${b.kind}:${b.label ?? "none"}:${String(i)}`}>
                <Block block={b} lit={lit} query={query} onPick={setPicked} />
                {picked !== null && b.label === picked && b.kind !== "article" && (
                  <div
                    role="dialog"
                    aria-label={COPY.reader.citedBy}
                    className="mt-[4px] ml-[43px] rounded-[10px] bg-card p-[8px] text-dense shadow-e2"
                    data-passage-popover={picked}
                  >
                    <div className="text-meta text-ink-3">{COPY.reader.citedBy}</div>
                    <ul>
                      {(citing[picked] ?? []).map((d) => (
                        <li key={d}>{d}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ))
          )}
        </article>
      </div>
    </section>
  );
}

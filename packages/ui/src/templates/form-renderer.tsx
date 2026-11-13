// T17 FormRendererLayout (F-07-T18; F-07 §G5; handoff T17 and TPL-17). The return's frame for the
// rendered form: the subbar and tabsbar slots with the Workbook · Form toggle, the 120 thumbnail
// rail (96 × 124 pages, the selected ring, a page's diagnostic count, a Missing placeholder), the
// form page on the E5 SourceViewer pipeline (its capsules, Download only in the ⋯ menu the caller
// supplies, Show traces outlining the manifest's regions) and the right 330 pane: the K-1 list,
// the Total = Schedule K tally pill (the server's tie state; the kit never sums) and the
// diagnostics, each with Go to (the page and the field lit by its manifest `match_id`).
//
// The face holds no editable control (C11: the form is rendered, never typed into). Firm-only.
import { type JSX, type ReactNode, useState } from "react";
import { cn } from "../cn";
import { amount } from "../format";
import { Button } from "../components/button";
import type { MenuItem } from "../components/popover";
import { Pill } from "../components/pill";
import { Segmented } from "../components/tabs";
import { SkeletonRows } from "../components/states";
import { useMatchStore } from "../tracing/match";
import type { MatchId } from "../tracing/types";
import { SourceViewer } from "../viewer/source-viewer";
import type { ViewerFile } from "../viewer/types";

export const FORM_GEOMETRY = { rail: 120, thumb: { w: 96, h: 124 }, pane: 330 } as const;

export type FormMode = "workbook" | "form";

export interface FormThumb {
  n: number;
  /** The server-rendered page image (the viewer's own rule: same-origin, blob or PNG data). */
  src: string | null;
  diagnostics?: number;
}

export interface K1ListRow {
  id: string;
  name: string;
  /** A decimal string, formatted, never summed. */
  amount: string | null;
  status: string;
}

export interface FormDiagnostic {
  id: string;
  severity: "error" | "warning";
  text: string;
  page: number;
  /** The manifest field's `match_id`: Go to lights it. A diagnostic without one goes to the page. */
  match: MatchId | null;
}

export interface FormRendererLayoutProps {
  subbar?: ReactNode;
  tabsbar?: ReactNode;
  mode: FormMode;
  onMode?: (mode: FormMode) => void;
  thumbs: readonly FormThumb[];
  page: number;
  onPage?: (n: number) => void;
  /** The rendered form (pages, the manifest's regions, masks). */
  file: ViewerFile | null;
  /** The ⋯ menu: the only place Download may appear. */
  menu?: readonly MenuItem[];
  k1s: readonly K1ListRow[];
  /** "Total = Schedule K": the server's tie state and difference. */
  total: { state: "tie" | "off" | "pending"; difference?: string | null };
  diagnostics: readonly FormDiagnostic[];
  loading?: boolean;
  className?: string;
}

function whole(value: string | null): string {
  if (value === null) return "—";
  return amount(value, "whole").text;
}

function Thumbs({
  thumbs,
  page,
  onPage,
}: {
  thumbs: readonly FormThumb[];
  page: number;
  onPage?: ((n: number) => void) | undefined;
}): JSX.Element {
  const { w, h } = FORM_GEOMETRY.thumb;
  return (
    <nav
      aria-label="Pages"
      style={{ width: FORM_GEOMETRY.rail }}
      className="flex flex-none flex-col items-center gap-[10px] overflow-y-auto py-[12px]"
    >
      {thumbs.map((t) => (
        <button
          key={t.n}
          type="button"
          aria-label={`Page ${String(t.n)}`}
          aria-current={t.n === page ? "page" : undefined}
          onClick={() => onPage?.(t.n)}
          style={{ width: w, height: h }}
          className={cn(
            "relative flex-none overflow-hidden rounded-[4px] bg-card shadow-e1",
            t.n === page && "ring-[1.5px] ring-ink",
          )}
        >
          {t.src === null ? (
            <span className="flex h-full items-center justify-center text-[11px] text-ink-3">
              Missing
            </span>
          ) : (
            <img src={t.src} alt="" className="h-full w-full object-cover" />
          )}
          {t.diagnostics ? (
            <span
              data-diagnostics={t.diagnostics}
              className="absolute right-[4px] top-[4px] rounded-pill bg-red-tint px-[5px] text-[10px] text-red-ink"
            >
              {t.diagnostics}
            </span>
          ) : null}
        </button>
      ))}
    </nav>
  );
}

function RightPane({
  k1s,
  total,
  diagnostics,
  onGoTo,
}: {
  k1s: readonly K1ListRow[];
  total: FormRendererLayoutProps["total"];
  diagnostics: readonly FormDiagnostic[];
  onGoTo: (d: FormDiagnostic) => void;
}): JSX.Element {
  return (
    <aside
      style={{ width: FORM_GEOMETRY.pane }}
      className="flex min-h-0 flex-none flex-col overflow-y-auto rounded-pane bg-card"
    >
      <section aria-label="K-1s">
        <header className="flex h-[46px] items-center justify-center text-[14.5px] font-medium">
          K-1s
        </header>
        <ul>
          {k1s.map((k) => (
            <li
              key={k.id}
              className="flex min-h-[33px] items-center gap-[8px] px-[12px] text-body hairline-b"
            >
              <span className="min-w-0 flex-1 truncate">{k.name}</span>
              <span className="tabular-nums">{whole(k.amount)}</span>
              <span className="text-[11px] text-ink-3">{k.status}</span>
            </li>
          ))}
          <li
            data-total={total.state}
            className="flex min-h-[33px] items-center gap-[8px] px-[12px] text-body font-medium"
          >
            <span className="flex-1">Total = Schedule K</span>
            <Pill
              variant={
                total.state === "tie" ? "green" : total.state === "off" ? "amber" : "neutral"
              }
            >
              {total.state === "tie"
                ? "tie"
                : total.state === "off"
                  ? `off ${whole((total.difference ?? "").replace("-", "") || null)}`
                  : "Pending"}
            </Pill>
          </li>
        </ul>
      </section>
      <section aria-label="Diagnostics" className="mt-[10px]">
        <header className="flex h-[36px] items-center px-[12px] text-[12px] font-medium text-ink-3">
          Diagnostics
          {diagnostics.length > 0 ? (
            <span className="ml-[6px] rounded-pill bg-red-tint px-[5px] text-[10px] text-red-ink">
              {diagnostics.length}
            </span>
          ) : null}
        </header>
        <ul>
          {diagnostics.map((d) => (
            <li
              key={d.id}
              className="flex min-h-[33px] items-center gap-[8px] px-[12px] py-[4px] text-body hairline-b"
            >
              <span
                className={cn(
                  "size-[6px] flex-none rounded-pill",
                  d.severity === "error" ? "bg-red" : "bg-amber",
                )}
                aria-hidden
              />
              <span className="min-w-0 flex-1">{d.text}</span>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  onGoTo(d);
                }}
              >
                Go to
              </Button>
            </li>
          ))}
        </ul>
      </section>
    </aside>
  );
}

export function FormRendererLayout({
  subbar,
  tabsbar,
  mode,
  onMode,
  thumbs,
  page,
  onPage,
  file,
  menu = [],
  k1s,
  total,
  diagnostics,
  loading = false,
  className,
}: FormRendererLayoutProps): JSX.Element {
  const store = useMatchStore();
  const [traces, setTraces] = useState(false);
  const goTo = (d: FormDiagnostic): void => {
    onPage?.(d.page);
    if (d.match !== null) store.light(d.match);
  };
  return (
    <div data-template="T17" className={cn("flex min-h-0 flex-1 flex-col", className)}>
      {subbar ? <div className="flex-none">{subbar}</div> : null}
      <div className="flex flex-none items-center gap-[8px] px-[12px]">
        {tabsbar ? <div className="min-w-0 flex-1">{tabsbar}</div> : <span className="flex-1" />}
        <Segmented
          size="small"
          label="Workbook or form"
          options={["Workbook", "Form"]}
          active={mode === "form" ? "Form" : "Workbook"}
          {...(onMode === undefined
            ? {}
            : {
                onChange: (l: string) => {
                  onMode(l === "Form" ? "form" : "workbook");
                },
              })}
        />
        <Button
          variant="ghost"
          size="sm"
          aria-pressed={traces}
          onClick={() => {
            setTraces(!traces);
          }}
        >
          Show traces
        </Button>
      </div>
      <div className="flex min-h-0 flex-1 gap-[10px] p-[12px]">
        <Thumbs thumbs={thumbs} page={page} onPage={onPage} />
        <div className="flex min-h-0 min-w-0 flex-1 flex-col" data-form-face="">
          {loading || file === null ? (
            <SkeletonRows type="card" immediate label="Rendering the form" />
          ) : (
            <SourceViewer file={file} menu={menu} outlineCited={traces} scrollToLit />
          )}
        </div>
        <RightPane k1s={k1s} total={total} diagnostics={diagnostics} onGoTo={goTo} />
      </div>
    </div>
  );
}

// TAX-05 · Return › Review, Review preset (T-04-T21; handoff TAX-05) in fixture mode on T3
// 452 × 3: the review tree with Flag, Check and Info micro-pills at the viewer's level, the draft
// K-1 in the viewer, and the Sch E – K-1 matrix with the 2024 column on the sheets pane. A K-1 box
// and its matrix row share one match id, so hovering either lights both (purple only through the
// match tokens). Approving a document is a person's act at the viewer's level (the host posts
// `document.approve`); the count moves only from the server's answer, here the frame's.
import { Button, Icon, Pill } from "@abacus/ui";
import { type JSX, useState } from "react";
import {
  COPY,
  type Frame,
  MATRIX,
  REVIEW_AFTER,
  REVIEW_BEFORE,
  TREE,
  type TreeRow,
  WORKSHEET_ROWS,
} from "./copy";

export interface ReviewPresetProps {
  frame: Frame;
  /** The viewer may approve at their level (`document.approve` in allowed_actions). */
  canApprove?: boolean;
  /** Approve the selected document; the host posts and answers with the next frame. */
  onApprove?: (key: string) => void;
  /** ⚑ on a row: TAX-06 with the row's issue selected (c). */
  onFlag?: (issue: string) => void;
  /** ⓘ on a row: SHL-09 provenance. */
  onInfo?: (key: string) => void;
  /** e: SHL-12 h at Partner level, assignee Daniel Reyes. */
  onRequestFinal?: () => void;
}

function MicroPills({
  row,
  approvedHere,
  onFlag,
  onInfo,
}: {
  row: TreeRow;
  approvedHere: boolean;
  onFlag?: (() => void) | undefined;
  onInfo?: (() => void) | undefined;
}): JSX.Element {
  const pill =
    "flex h-[21px] items-center gap-[2px] rounded-[6px] bg-card px-[5px] text-[11px] shadow-e1";
  return (
    <span className="ml-auto flex shrink-0 items-center gap-[3px]">
      <button
        type="button"
        aria-label={row.flagged ? `Flag ${String(row.flagged)}` : "Flag"}
        className={`${pill} ${row.flagged ? "text-amber-ink" : "text-ink-3"}`}
        onClick={onFlag}
      >
        ⚑{row.flagged ? ` ${String(row.flagged)}` : ""}
      </button>
      <span
        data-check={approvedHere ? "approved" : "open"}
        aria-label={approvedHere ? "Approved at your level, 1" : "Not approved at your level"}
        className={`${pill} ${approvedHere ? "text-ink" : "text-ink-3"}`}
      >
        ✓{approvedHere ? <span className="text-ink-2"> 1</span> : null}
      </span>
      <button type="button" aria-label="Info" className={`${pill} text-ink-3`} onClick={onInfo}>
        ⓘ
      </button>
    </span>
  );
}

export function ReviewPreset({
  frame,
  canApprove = true,
  onApprove,
  onFlag,
  onInfo,
  onRequestFinal,
}: ReviewPresetProps): JSX.Element {
  const [lit, setLit] = useState<string | null>(frame === "a" ? "interest" : null);
  const approvedNow = frame === "b";
  const all = frame === "e";
  const review = all ? null : approvedNow ? REVIEW_AFTER : REVIEW_BEFORE;
  const selected = approvedNow ? "stmtA" : "k1";
  const sheets = frame === "d" ? "Worksheets" : "Leadsheets";
  if (frame === "f") {
    return (
      <div
        data-screen="TAX-05"
        data-frame="f"
        aria-busy="true"
        className="flex gap-[10px] p-[12px]"
      >
        {[0, 1, 2].map((i) => (
          <div key={i} data-skeleton className="h-[700px] w-[452px] rounded-pane bg-nested" />
        ))}
        <span className="sr-only">{COPY.loading}</span>
      </div>
    );
  }
  return (
    <div data-screen="TAX-05" data-frame={frame} className="flex flex-col">
      <header className="flex h-[42px] items-center justify-center gap-[8px]">
        <span className="text-[15px] font-medium">{COPY.title}</span>
        <span className="text-ink-2">{COPY.client}</span>
        <Pill variant="neutral">{COPY.state}</Pill>
      </header>
      <nav aria-label="Return" className="flex h-[44px] items-center justify-center gap-[6px]">
        {COPY.tabs(review).map((t) => (
          <span
            key={t}
            data-tab={t}
            aria-current={t.startsWith("Review") ? "page" : undefined}
            className={`rounded-[8px] px-[10px] py-[4px] text-[13px] ${t.startsWith("Review") ? "bg-card font-medium shadow-e1" : "text-ink-2"}`}
          >
            {t}
          </span>
        ))}
      </nav>
      <div className="flex gap-[10px] px-[12px] pb-[12px]">
        <section
          aria-label={COPY.tree}
          className="flex w-[452px] flex-col rounded-pane bg-card shadow-e1"
        >
          <h2 className="flex h-[46px] items-center justify-center text-[14.5px] font-medium">
            {COPY.tree}
          </h2>
          {all ? (
            <div
              data-banner="all-approved"
              className="mx-[10px] rounded-[8px] bg-green-tint px-[10px] py-[8px] text-[12.5px] text-green-ink"
            >
              {COPY.allApproved}
            </div>
          ) : null}
          <ul className="flex flex-col px-[8px]">
            {TREE.map((g) => (
              <li key={g.head}>
                <p className="px-[6px] pt-[8px] text-[12px] font-medium text-ink-2">{g.head}</p>
                {g.subs.map((s) => (
                  <div key={s.head}>
                    <p className="px-[18px] text-[11.5px] text-ink-3">{s.head}</p>
                    {s.rows.map((r) => {
                      const approvedHere =
                        all || r.approved === true || (approvedNow && r.key === "stmtA");
                      return (
                        <div
                          key={r.key}
                          data-row={r.key}
                          aria-current={r.key === selected ? "true" : undefined}
                          className={`flex h-[29px] items-center gap-[6px] rounded-[6px] pl-[28px] pr-[4px] text-[12.5px] ${r.key === selected ? "bg-sel-bg font-medium" : ""}`}
                        >
                          <Icon name="file-text" size={13} className="text-ink-3" />
                          <span className="truncate">{r.title}</span>
                          {r.tag ? (
                            <span className="shrink-0 rounded-[5px] bg-nested px-[4px] text-[11px] text-ink-2">
                              {r.tag}
                            </span>
                          ) : null}
                          <MicroPills
                            row={r}
                            approvedHere={approvedHere}
                            onFlag={
                              r.flagged && onFlag
                                ? () => {
                                    onFlag(COPY.flaggedIssue);
                                  }
                                : undefined
                            }
                            onInfo={
                              onInfo
                                ? () => {
                                    onInfo(r.key);
                                  }
                                : undefined
                            }
                          />
                        </div>
                      );
                    })}
                  </div>
                ))}
              </li>
            ))}
          </ul>
          <footer className="mt-auto flex flex-col gap-[8px] p-[10px]">
            {all ? (
              <Button variant="primary" disabled title={COPY.draftBlocks} onClick={onRequestFinal}>
                {COPY.requestFinal}
              </Button>
            ) : approvedNow ? (
              <Button variant="secondary">{COPY.unapprove}</Button>
            ) : (
              <Button
                variant="primary"
                disabled={!canApprove}
                onClick={() => onApprove?.(selected)}
              >
                {COPY.approve}
              </Button>
            )}
            {all ? <p className="text-[11px] text-ink-3">{COPY.draftBlocks}</p> : null}
            <Button variant="secondary">{COPY.issue}</Button>
          </footer>
          {approvedNow ? (
            <p role="status" data-toast className="sr-only">
              {COPY.toast}
            </p>
          ) : null}
        </section>
        <section
          aria-label={COPY.viewer}
          className="flex w-[452px] flex-col rounded-pane bg-card shadow-e1"
        >
          <h2 className="flex h-[46px] items-center justify-center text-[13px] font-medium">
            {COPY.viewer}
          </h2>
          <div className="relative m-[10px] flex-1 rounded-[4px] bg-surface p-[12px] text-[11.5px]">
            <p className="text-ink-3">Schedule K-1 (Form 1065) 2025 · DRAFT · pre-release</p>
            <button
              type="button"
              data-box="5"
              data-lit={lit === "interest"}
              onMouseEnter={() => {
                setLit("interest");
              }}
              onMouseLeave={() => {
                setLit(frame === "a" ? "interest" : null);
              }}
              className={`mt-[8px] block rounded-[3px] px-[4px] ${lit === "interest" ? "bg-match-bg inset-ring-1 inset-ring-match-line" : ""}`}
            >
              5 Interest income 4,600
            </button>
            <p>2 Net rental real estate income 307,900</p>
            <p>18A 1,550 · 19A 150,000</p>
          </div>
        </section>
        <section
          aria-label="Sheets"
          className="flex w-[452px] flex-col rounded-pane bg-card shadow-e1"
        >
          <div role="tablist" className="flex h-[46px] items-center gap-[6px] px-[10px]">
            {COPY.sheetTabs.map((t) => (
              <span
                key={t}
                role="tab"
                aria-selected={t === sheets}
                className={`text-[12.5px] ${t === sheets ? "font-medium" : "text-ink-2"}`}
              >
                {t}
              </span>
            ))}
          </div>
          {sheets === "Worksheets" ? (
            <div data-sheets="worksheets" className="px-[10px]">
              <p className="flex h-[34px] items-center gap-[6px] text-[13px] font-medium">
                {COPY.worksheet}
                <span className="rounded-[4px] bg-nested px-[4px] text-[11px]">{COPY.tsj}</span>
              </p>
              {WORKSHEET_ROWS.map((w) => (
                <div key={w.label} className="flex h-[42px] items-center gap-[8px] text-[13px]">
                  <span className="text-ink-2">{w.label}</span>
                  <span className="ml-auto tabular-nums">{w.value}</span>
                  {w.chips.map((c) => (
                    <span key={c} className="rounded-[5px] bg-nested px-[4px] text-[11px]">
                      {c}
                    </span>
                  ))}
                </div>
              ))}
            </div>
          ) : (
            <table data-sheets="matrix" className="mx-[10px] text-[13px]">
              <thead>
                <tr className="h-[41px] font-medium">
                  <th scope="col" className="text-left text-ink-2">
                    {COPY.entities}
                  </th>
                  <th scope="col" className="text-right">
                    {COPY.entity}
                  </th>
                  <th scope="col" className="text-right text-ink-3">
                    {COPY.pyHead}
                  </th>
                </tr>
              </thead>
              <tbody>
                {MATRIX.map((m) => {
                  const on = m.lit === true && lit === "interest";
                  return (
                    <tr
                      key={m.label}
                      data-matrix={m.label}
                      data-lit={on}
                      onMouseEnter={
                        m.lit
                          ? () => {
                              setLit("interest");
                            }
                          : undefined
                      }
                      className={`h-[41px] ${on ? "bg-match-bg" : ""}`}
                    >
                      <th
                        scope="row"
                        className={`text-left font-normal text-ink-2 ${on ? "font-medium" : ""}`}
                      >
                        {m.label}
                      </th>
                      <td className="text-right tabular-nums">
                        {m.status ? <Pill variant="amber">{m.cy}</Pill> : m.cy}
                        {m.note ? (
                          <span className="block text-[11.5px] text-amber-ink">⚑ {m.note}</span>
                        ) : null}
                      </td>
                      <td className="text-right tabular-nums text-ink-3">{m.py}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </section>
      </div>
    </div>
  );
}

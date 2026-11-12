// TXI-03 · State residency & allocation (T-04-T41; handoff TXI-03) in fixture mode, T6 two-pane:
// residency 560 · allocation 806, with the control bar and the tally strip. Facts carry citation
// chips; the ask card holds code's options with the Recommended tag; Confirm opens the SHL-10-style
// confirmation (the host's) and is shown to reviewers only; Ask the client previews the POR-04
// question with Send for reviewers only (the agent never sends). The tables carry no "$".
import { Button } from "@abacus/ui";
import { type JSX, useState } from "react";
import {
  CELL_LINKS,
  COPY,
  CREDITS,
  CREDIT_COLUMNS,
  FACTS,
  type Frame,
  INCOME,
  INCOME_COLUMNS,
  NOTES,
  OPTIONS,
  TALLIES,
} from "./copy";

export interface ResidencyAllocationProps {
  frame: Frame;
  /** Whether the viewer is a reviewer (Confirm and Send are theirs; never the agent's). */
  reviewer?: boolean;
  /** "Confirm residency": the SHL-10-style confirmation (the host's). */
  onConfirm?: (option: string) => void;
  /** "Send" in the Ask the client sheet: POR-04 through the host (a person's action). */
  onSend?: () => void;
  /** A citation chip: SHL-08 with the region lit. */
  onSource?: (chip: string) => void;
  /** A table cell: TXI-01 with the field selected, or TXI-02 treatment 7. */
  onCell?: (target: string) => void;
}

function Table({
  title,
  columns,
  rows,
  onCell,
}: {
  title: string;
  columns: readonly string[];
  rows: readonly (readonly string[])[];
  onCell?: ((target: string) => void) | undefined;
}): JSX.Element {
  return (
    <div className="overflow-hidden rounded-[12px] bg-surface shadow-e1">
      <div className="px-[12px] py-[8px] text-[13px] font-medium">{title}</div>
      <table className="w-full border-collapse text-[12.5px]" data-table={title}>
        <thead>
          <tr className="h-[30px] text-left text-[11.5px] text-ink-3">
            {columns.map((c) => (
              <th key={c} className="px-[8px] font-medium">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const total = row[0] === "TOTAL";
            return (
              <tr
                key={row[0]}
                data-row={row[0]}
                className={`h-[32px] border-t border-hair ${total ? "font-medium" : ""}`}
              >
                {row.map((cell, i) => {
                  const column = columns[i] ?? "";
                  const link =
                    CELL_LINKS[column] ??
                    (title === COPY.table2 && i === 4 ? CELL_LINKS.PTET : undefined);
                  return (
                    <td
                      key={`${row[0] ?? ""}-${column}`}
                      className={`px-[8px] ${i > 0 ? "tabular-nums" : ""}`}
                    >
                      {link && !total && cell !== "—" && cell !== "" ? (
                        <button type="button" data-cell={link} onClick={() => onCell?.(link)}>
                          {cell}
                        </button>
                      ) : (
                        cell
                      )}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function ResidencyAllocation({
  frame,
  reviewer = true,
  onConfirm,
  onSend,
  onSource,
  onCell,
}: ResidencyAllocationProps): JSX.Element {
  const conflict = frame === "c" || frame === "d";
  const recommendedKey = conflict ? "full_year_nys_part_year_nyc" : "full_year_nys_nyc";
  const [selected, setSelected] = useState<string>(recommendedKey);
  const [asking, setAsking] = useState(frame === "d");
  const confirmed = frame === "b";
  const loading = frame === "e";
  return (
    <div data-screen="TXI-03" data-frame={frame} className="flex flex-col bg-canvas">
      <div className="flex h-[42px] items-center gap-[10px] px-[12px] text-[13px]">
        <span className="text-ink-2">{COPY.subbar.checkpoints}</span>
        <span className="rounded-[7px] bg-surface px-[6px] text-amber-ink shadow-e1">
          {COPY.subbar.sync}
        </span>
        <span className="flex-1 text-center">
          <span className="font-medium">{COPY.subbar.form}</span>{" "}
          <span className="text-ink-2">{COPY.subbar.client}</span>{" "}
          <span className="rounded-[999px] bg-surface-2 px-[6px] text-[11.5px]">
            {COPY.subbar.state}
          </span>
        </span>
        <span className="text-ink-2">{COPY.subbar.assistant}</span>
      </div>
      <nav
        aria-label="Return tabs"
        className="flex h-[50px] items-center gap-[12px] px-[12px] text-[13px]"
      >
        <span className="flex gap-[4px]">
          {COPY.tabs.map((t) => (
            <span
              key={t}
              className={
                t.startsWith("Review")
                  ? "rounded-[7px] bg-surface px-[8px] font-medium shadow-e1"
                  : "px-[8px] text-ink-2"
              }
            >
              {t}
            </span>
          ))}
        </span>
        <span className="flex gap-[4px]">
          {COPY.subtabs.map((t) => (
            <span
              key={t}
              className={
                t.startsWith("Residency")
                  ? "rounded-[7px] bg-surface px-[8px] font-medium shadow-e1"
                  : "px-[8px] text-ink-2"
              }
            >
              {t}
            </span>
          ))}
        </span>
      </nav>
      <div className="flex h-[44px] items-center px-[12px] text-[13px]">
        <span className="flex gap-[4px]">
          {COPY.control.map((c) => (
            <span
              key={c}
              className={
                c === "Residency"
                  ? "rounded-[7px] bg-surface px-[8px] font-medium shadow-e1"
                  : "px-[8px] text-ink-2"
              }
            >
              {c}
            </span>
          ))}
        </span>
        <span className="flex-1 text-center text-[14.5px] font-medium">{COPY.title}</span>
        <Button variant="ghost">{COPY.excel}</Button>
      </div>
      <div className="flex h-[52px] items-center gap-[18px] px-[12px]" data-tallies>
        {TALLIES.map((t) => {
          const value = t.key === "residency" && confirmed ? "Confirmed" : t.value;
          const tone = t.key === "residency" && confirmed ? "green" : t.tone;
          return (
            <span key={t.key} data-tally={t.key} className="flex flex-col">
              <span className="text-[11px] uppercase text-ink-3">{t.label}</span>
              <span
                className={`text-[14px] font-medium tabular-nums ${
                  tone === "green" ? "text-green-ink" : tone === "amber" ? "text-amber-ink" : ""
                }`}
              >
                {value}
              </span>
            </span>
          );
        })}
      </div>
      <div className="flex gap-[10px] px-[12px] pb-[12px]">
        <section aria-label="Residency" className="flex w-[560px] flex-col gap-[10px]">
          {confirmed ? (
            <div
              role="status"
              data-banner="confirmed"
              className="rounded-[10px] bg-green-tint px-[12px] py-[8px] text-[12.5px] text-green-ink"
            >
              {COPY.confirmed}
            </div>
          ) : null}
          {conflict ? (
            <div
              role="alert"
              data-banner="action_required"
              className="rounded-[10px] bg-red-tint px-[12px] py-[8px] text-[12.5px] text-red-ink"
            >
              {COPY.actionRequired}
            </div>
          ) : null}
          <div className="rounded-[12px] bg-surface shadow-e1">
            <div className="flex h-[46px] items-center px-[12px] text-[13px] font-medium">
              {COPY.residencyHeader}
            </div>
            {FACTS.map((f) => (
              <div
                key={f.key}
                data-fact={f.key}
                className="flex min-h-[33px] items-center gap-[8px] px-[12px] text-[12.5px]"
              >
                <span className="w-[200px] text-ink-2">{f.label}</span>
                <span className="flex-1">{f.value}</span>
                <button
                  type="button"
                  data-chip={f.chip}
                  onClick={() => onSource?.(f.chip)}
                  className="rounded-[5px] bg-surface-2 px-[5px] text-[11px] text-ink-2"
                >
                  {f.chip}
                </button>
              </div>
            ))}
          </div>
          <div className="rounded-[12px] bg-surface shadow-e2" data-ask>
            <div className="flex h-[36px] items-center gap-[6px] px-[12px] text-[14px] font-medium">
              <span className="rounded-[999px] bg-surface-2 px-[6px] text-[12px]">?</span>
              {COPY.askTitle}
            </div>
            <div
              role="radiogroup"
              aria-label={COPY.askTitle}
              className="flex flex-col gap-[8px] px-[12px] pb-[8px]"
            >
              {OPTIONS.map((o) => (
                <label key={o.key} data-option={o.key} className="flex gap-[8px]">
                  <input
                    type="radio"
                    name="residency"
                    checked={selected === o.key}
                    onChange={() => {
                      setSelected(o.key);
                    }}
                    disabled={confirmed}
                  />
                  <span className="flex flex-col">
                    <span className="text-[13.5px]">
                      {o.title}
                      {o.key === recommendedKey ? (
                        <span
                          data-recommended
                          className="ml-[6px] rounded-[5px] bg-surface-2 px-[5px] text-[11px] font-medium"
                        >
                          {COPY.recommended}
                        </span>
                      ) : null}
                    </span>
                    <span className="text-[12.5px] leading-[1.35] text-ink-2">{o.detail}</span>
                  </span>
                </label>
              ))}
            </div>
            {confirmed ? null : (
              <div className="flex justify-between px-[12px] py-[10px]">
                <Button
                  variant={conflict ? "primary" : "secondary"}
                  onClick={() => {
                    setAsking(true);
                  }}
                >
                  {COPY.askClient}
                </Button>
                {reviewer ? (
                  <Button
                    variant={conflict ? "secondary" : "primary"}
                    onClick={() => onConfirm?.(selected)}
                  >
                    {COPY.confirm}
                  </Button>
                ) : null}
              </div>
            )}
          </div>
          {asking ? (
            <div
              role="dialog"
              aria-label="Ask the client"
              data-sheet
              className="rounded-[12px] bg-surface p-[12px] shadow-e2"
            >
              <div className="text-[12px] text-ink-3">{COPY.sheetTo}</div>
              <p className="py-[6px] text-[13.5px]">{COPY.sheetQuestion}</p>
              <ul className="flex gap-[8px] text-[12.5px]">
                {COPY.sheetOptions.map((o) => (
                  <li key={o} className="rounded-[7px] bg-surface-2 px-[8px] py-[4px]">
                    {o}
                  </li>
                ))}
              </ul>
              {reviewer ? (
                <div className="flex justify-end pt-[8px]">
                  <Button onClick={onSend}>{COPY.send}</Button>
                </div>
              ) : null}
            </div>
          ) : null}
        </section>
        <section aria-label="State allocation" className="flex w-[806px] flex-col gap-[10px]">
          <div className="flex h-[46px] items-center rounded-[12px] bg-surface px-[12px] text-[13px] font-medium shadow-e1">
            {COPY.allocationHeader}
          </div>
          {loading ? (
            <div
              aria-busy="true"
              data-skeleton
              className="flex flex-col gap-[6px] rounded-[12px] bg-surface p-[12px] shadow-e1"
            >
              <span className="text-[12.5px] text-ink-3">{COPY.loading}</span>
              {[0, 1, 2, 3, 4].map((i) => (
                <span key={i} className="h-[24px] rounded-[6px] bg-surface-2" />
              ))}
            </div>
          ) : (
            <>
              <Table title={COPY.table1} columns={INCOME_COLUMNS} rows={INCOME} onCell={onCell} />
              <Table title={COPY.table2} columns={CREDIT_COLUMNS} rows={CREDITS} onCell={onCell} />
              <div className="rounded-[12px] bg-surface shadow-e1">
                {NOTES.map(([k, v]) => (
                  <div
                    key={k}
                    className="flex min-h-[33px] gap-[8px] px-[12px] py-[6px] text-[12.5px]"
                  >
                    <span className="w-[200px] text-ink-2">{k}</span>
                    <span className="flex-1">{v}</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}

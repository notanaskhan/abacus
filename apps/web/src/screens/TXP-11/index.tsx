// TXP-11 · Workpaper — Ridgeline workbook, sheet 05 Capital (T-05-T38; docs/screens/TXP-11.md;
// handoff TXP-11 A–E) on the kit's WorkbookGrid: name box, formula bar, the grid, sheet tabs and
// the "Sheet!Cell" footer, under a bar with "Open in Excel" and the version picker. A: arriving
// from the TXP-10 issue with H12 selected and H8:H12, J13, J15 lit; B: the fix proposed (H8:H12
// "Proposed"); B2: approved (J13 = J15 = 6,866,200, the 05 tab's amber dot gone); C: 01 Trial
// Balance, I18 "=F18+G18+H18"; E: editing, the host saves through PUT …/workbook/cells with the
// cell's version (a 409 reads the conflict line). The grid shows the server's values; nothing here
// computes a figure (ADR-050).
import type { WorkbookCellOut, WorkbookSheetCellsOut } from "@abacus/api-client";
import {
  Button,
  Picker,
  type WorkbookCell,
  WorkbookGrid,
  type WorkbookSheetTab,
  amount,
  pct,
} from "@abacus/ui";
import type { JSX } from "react";
import { COPY, SHEETS } from "./copy";

export type Txp11Sheet = (typeof SHEETS)[number];

/** The sheet key the server addresses ("05") from its tab title. */
export const keyOf = (title: string): string => title.slice(0, 2);

const PERCENT_COLUMNS = new Set(["B", "C"]);

/** A server cell as the grid shows it: numbers whole with credits in parentheses, the 05 sheet's
 * two percentage columns as percentages, text as it is. Formatting only. */
export function display(sheet: string, c: WorkbookCellOut): string {
  const raw = c.value ?? "";
  if (raw === "") return "";
  if (!/^-?\d+(\.\d+)?$/u.test(raw)) return raw;
  const column = c.address.replace(/\d+$/u, "");
  const row = Number(c.address.replace(/^[A-Z]+/u, ""));
  if (sheet === "05" && PERCENT_COLUMNS.has(column) && row >= 8) {
    return raw === "0" ? "—" : pct(raw);
  }
  return amount(raw, "whole", { zero: "explicit" }).text;
}

export function gridCells(
  sheet: string,
  data: WorkbookSheetCellsOut | undefined,
  expected: Readonly<Record<string, string>> = {},
): Record<string, WorkbookCell> {
  const out: Record<string, WorkbookCell> = {};
  for (const c of data?.cells ?? []) {
    const text = display(sheet, c);
    out[c.address] = {
      display: text,
      formula: c.formula ?? null,
      align: /^[(\d$—-]/u.test(text) && text !== "" ? "right" : "left",
      ...(c.state === "flagged" ? { proposed: true } : {}),
    };
  }
  for (const [address, formula] of Object.entries(expected)) {
    out[address] = { ...(out[address] ?? { display: "" }), expected: formula };
  }
  return out;
}

export interface TXP11Props {
  sheet: Txp11Sheet;
  data?: WorkbookSheetCellsOut | undefined;
  selected: string;
  /** Cells the open issue cites (A, B). */
  cited?: readonly string[];
  /** The 05 tab carries an open issue (A, B; gone in B2). */
  openIssue?: boolean;
  /** A prior run's version: no editing (the version picker). */
  readOnly?: boolean;
  /** The last save answered 409 `cell_version_conflict`. */
  conflict?: boolean;
  saving?: boolean;
  onSelect: (address: string) => void;
  onSheet?: (sheet: Txp11Sheet) => void;
  /** Enter in the editor: the host saves `value` for `sheet!address`. */
  onCommit?: (address: string, value: string) => void;
  onReload?: () => void;
  onOpenInExcel?: () => void;
  onOpenIssue?: () => void;
  /** T-05-T38 rest (DEC-4630): the finished runs' versions, newest first, and the one shown. */
  versions?: readonly number[];
  version?: number | undefined;
  onVersion?: (version: number) => void;
  /** The selected cell's provenance (SHL-09, a3) and citations (SHL-07, a2). */
  onProvenance?: (address: string) => void;
  onCitations?: (address: string) => void;
}

/** How many citations the server lists on a cell of the sheet. */
export function citationCount(data: WorkbookSheetCellsOut | undefined, address: string): number {
  return data?.cells.find((c) => c.address === address)?.citation_ids?.length ?? 0;
}

export function TXP11({
  sheet,
  data,
  selected,
  cited = [],
  openIssue = false,
  readOnly = false,
  conflict = false,
  saving = false,
  onSelect,
  onSheet,
  onCommit,
  onReload,
  onOpenInExcel,
  onOpenIssue,
  versions = [],
  version,
  onVersion,
  onProvenance,
  onCitations,
}: TXP11Props): JSX.Element {
  const shown = version ?? versions[0] ?? data?.version ?? 1;
  const cites = citationCount(data, selected);
  const key = keyOf(sheet);
  const expected = key === "05" && openIssue ? { H12: COPY.expectedH12 } : {};
  const sheets: WorkbookSheetTab[] = SHEETS.map((title) => ({
    title,
    ...(title === "05 Capital" && openIssue ? { openIssue: true } : {}),
  }));
  return (
    <div data-screen="TXP-11" data-sheet={key} className="flex min-h-0 flex-1 flex-col">
      <div className="flex h-[40px] flex-none items-center gap-[8px] px-[12px]">
        {openIssue ? (
          <button
            type="button"
            className="rounded-[6px] border border-match-line bg-match-bg px-[8px] py-[2px] text-[11.5px] text-ink"
            onClick={onOpenIssue}
          >
            {COPY.linkedIssue}
          </button>
        ) : null}
        {conflict ? (
          <span role="alert" className="text-[11.5px] text-ink-2">
            {COPY.conflict}{" "}
            <Button variant="ghost" size="sm" onClick={onReload}>
              {COPY.reload}
            </Button>
          </span>
        ) : null}
        {saving ? <span className="text-[11.5px] text-ink-3">{COPY.saving}</span> : null}
        <span className="flex-1" />
        {onProvenance === undefined ? null : (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              onProvenance(selected);
            }}
          >
            {COPY.provenance}
          </Button>
        )}
        {onCitations === undefined || cites === 0 ? null : (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              onCitations(selected);
            }}
          >
            {COPY.citations(cites)}
          </Button>
        )}
        <Button variant="ghost" size="sm" icon="square-arrow-out-up-right" onClick={onOpenInExcel}>
          {COPY.openInExcel}
        </Button>
        {versions.length > 1 && onVersion !== undefined ? (
          <Picker
            label={COPY.versions}
            options={versions.map((n) => ({ value: String(n), label: COPY.version(n) }))}
            value={String(shown)}
            onChange={(v) => {
              onVersion(Number(v));
            }}
          />
        ) : (
          <span className="text-[12px] text-ink-2">{COPY.version(shown)}</span>
        )}
        {readOnly ? <span className="text-[12px] text-ink-3">{COPY.readOnlyVersion}</span> : null}
      </div>
      <div className="min-h-0 flex-1 px-[12px] pb-[12px]">
        <WorkbookGrid
          label={COPY.grid}
          sheet={sheet}
          sheets={sheets}
          columns={11}
          rows={key === "01" ? 21 : 16}
          cells={gridCells(key, data, expected)}
          cited={cited}
          selected={selected}
          onSelect={onSelect}
          onSheet={(title) => onSheet?.(title as Txp11Sheet)}
          {...(onCommit === undefined ? {} : { onCommit })}
          footerMeta={openIssue ? `${COPY.citedBy} · ${COPY.evidence}` : ""}
          readOnly={readOnly || onCommit === undefined}
          widths={{
            0: 220,
            1: 70,
            2: 70,
            3: 110,
            4: 110,
            5: 130,
            6: 110,
            7: 130,
            8: 110,
            9: 120,
            10: 90,
          }}
        />
      </div>
    </div>
  );
}

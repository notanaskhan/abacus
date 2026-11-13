// TXP-02's overlays (T-05-T37 rest; TASK-7634; DEC-4629; handoff TXP-02 a2, a3, e2):
// - a2 · Cell provenance: SHL-09's tray for one of the row's sheet 01 cells (UTB, AJE, RJE, ATB),
//   the address the server names (`WorkbookTbRowOut.cells`); the tray is P-04's field history.
// - a3 · The entry drawer (O2): an AJE, RJE or TJE with its lines, memo and named approval, all
//   the server's (C8); approving and proposing stay A-06's own screens.
// - e2 · The line picker (O1 300): the published set's mappable lines with search; a pick goes
//   to `POST …/mappings`. The tax reviewer's pick maps the account; anyone else's is a review note
//   proposing the line (the server decides which; the screen shows its answer, never guesses).
import type { WorkbookFormLineOut, WorkbookJournalEntryOut } from "@abacus/api-client";
import { Button, Drawer, SearchField, Segmented, amount } from "@abacus/ui";
import { type JSX, useState } from "react";
import { ProvenanceTray } from "../SHL-09";
import { COPY } from "./copy";

const CELL_COLUMNS = ["utb", "aje", "rje", "atb"] as const;
type CellColumn = (typeof CELL_COLUMNS)[number];
const COLUMN_LABEL: Readonly<Record<CellColumn, string>> = {
  utb: COPY.columns.utb,
  aje: COPY.columns.aje,
  rje: COPY.columns.rje,
  atb: COPY.columns.atb,
};

export interface CellTarget {
  returnId: string;
  accountCode: string;
  accountName: string;
  /** The row's sheet 01 cells by column, as the server names them ("01!F10"). */
  cells: Readonly<Record<string, string>>;
}

/** a2: the row's cells, ATB first shown (the handoff's example is an ATB). */
export function CellDrawer({
  target,
  onClose,
}: {
  target: CellTarget | null;
  onClose: () => void;
}): JSX.Element {
  const [column, setColumn] = useState<CellColumn>("atb");
  const address = target?.cells[column];
  return (
    <Drawer
      open={target !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={target === null ? COPY.cellTitle : `${target.accountCode} ${target.accountName}`}
      description={COPY.cellTitle}
      size="sm"
      peek
    >
      {target === null ? null : (
        <div className="flex flex-col gap-[10px]">
          <Segmented
            size="small"
            label={COPY.cellColumns}
            options={CELL_COLUMNS.map((c) => COLUMN_LABEL[c])}
            active={COLUMN_LABEL[column]}
            onChange={(label: string) => {
              const found = CELL_COLUMNS.find((c) => COLUMN_LABEL[c] === label);
              if (found !== undefined) setColumn(found);
            }}
          />
          {address === undefined ? (
            <p className="text-meta text-ink-3">{COPY.noCell}</p>
          ) : (
            <>
              <p className="text-meta font-medium tabular-nums text-ink-2">{address}</p>
              <ProvenanceTray
                key={address}
                field={{ type: "tax_workbook", id: target.returnId, fieldKey: address }}
              />
            </>
          )}
        </div>
      )}
    </Drawer>
  );
}

/** a3: one entry, lines in the TB grammar ("$", whole dollars). */
export function EntryDrawer({
  entry,
  onClose,
}: {
  entry: WorkbookJournalEntryOut | null;
  onClose: () => void;
}): JSX.Element {
  return (
    <Drawer
      open={entry !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={entry?.reference ?? COPY.entryLines}
      size="sm"
    >
      {entry === null ? null : (
        <div className="flex flex-col gap-[12px]">
          <table className="w-full text-body tabular-nums" aria-label={COPY.entryLines}>
            <thead>
              <tr className="text-meta text-ink-3">
                <th className="py-[4px] text-left font-medium">{COPY.columns.name}</th>
                <th className="py-[4px] text-right font-medium">{COPY.entryDebit}</th>
                <th className="py-[4px] text-right font-medium">{COPY.entryCredit}</th>
              </tr>
            </thead>
            <tbody>
              {(entry.lines ?? []).map((ln) => (
                <tr key={`${ln.account_code}:${ln.debit}:${ln.credit}`}>
                  <td className="py-[4px]">
                    {ln.account_code} {ln.account_name ?? ""}
                  </td>
                  <td className="py-[4px] text-right">
                    {Number(ln.debit) === 0 ? "—" : amount(ln.debit, "dollars").text}
                  </td>
                  <td className="py-[4px] text-right">
                    {Number(ln.credit) === 0 ? "—" : amount(ln.credit, "dollars").text}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {entry.description === null || entry.description === undefined ? null : (
            <div>
              <p className="text-kpi-label text-ink-3 uppercase">{COPY.entryMemo}</p>
              <p className="text-body text-ink">{entry.description}</p>
            </div>
          )}
          {entry.approval === null || entry.approval === undefined ? null : (
            <p className="text-meta text-ink-2">{entry.approval}</p>
          )}
        </div>
      )}
    </Drawer>
  );
}

/** e2: the line picker over the published set; keyboard reaches every line (a list of buttons). */
export function LinePicker({
  accountCode,
  lines,
  query,
  onQuery,
  onPick,
  onClose,
  outcome,
  busy = false,
}: {
  accountCode: string | null;
  lines: readonly WorkbookFormLineOut[];
  query: string;
  onQuery: (q: string) => void;
  onPick: (key: string) => void;
  onClose: () => void;
  /** The server's answer to the last pick. */
  outcome?: "mapped" | "flagged" | undefined;
  busy?: boolean;
}): JSX.Element {
  return (
    <Drawer
      open={accountCode !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={accountCode === null ? COPY.pickerTitle : `${COPY.pickerTitle} · ${accountCode}`}
      size="sm"
    >
      <div className="flex flex-col gap-[8px]">
        <SearchField
          label={COPY.pickerSearch}
          placeholder={COPY.pickerSearch}
          value={query}
          onChange={onQuery}
          className="w-full"
        />
        {outcome === undefined ? null : (
          <p role="status" className="text-meta text-ink-2">
            {outcome === "mapped" ? COPY.pickerMapped : COPY.pickerProposed}
          </p>
        )}
        {lines.length === 0 ? (
          <p className="text-meta text-ink-3">{COPY.pickerEmpty}</p>
        ) : (
          <ul aria-label={COPY.pickerTitle} className="flex max-h-[420px] flex-col overflow-auto">
            {lines.map((line) => (
              <li key={line.key}>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={busy}
                  className="w-full justify-start"
                  onClick={() => {
                    onPick(line.key);
                  }}
                >
                  {line.label}
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Drawer>
  );
}

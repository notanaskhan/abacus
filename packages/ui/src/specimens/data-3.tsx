import { type JSX, useEffect, useState } from "react";
import { DataGrid } from "../data/data-grid";
import { EvidenceTable } from "../data/evidence";
import { FieldBlock } from "../data/fields";
import { type GridColumn, type GridRow, GridTable } from "../data/grid";
import { amount } from "../format";
import type { TableColumn, TableRow } from "../data/types";
import { MatchScope, Matchable, useMatchStore } from "../tracing/match";
import type { MatchId } from "../tracing/types";
import { Held, Row, Sheet } from "./frame";
import {
  FELD_LEADSHEETS,
  LEADSHEET_COLUMNS,
  feldBox,
  feldWorksheets,
  leadsheetMatch,
} from "./feld-t3";
import { NORTHWIND_PLAN, NORTHWIND_TB, STAFF } from "./seed-figures";

// DataTable grammars 3 (F-05-T52; C-01 specs 04 and 05): the grid grammar on Northwind's trial
// balance workbook (the seed's, documents.py), the leadsheet grammar and the field rows on the T3
// handoff's Feld 2025 Form 1040 lines, and the E4 virtualiser on 1,000 fixture rows. Kit sample
// data (the audit program, Jamie Lin, the W-2 sample) is never ported.

const TB_FILE = "Northwind PY2025 trial balance.xlsx";
const TB_SHEET = "Trial balance";

const TB_COLUMNS: readonly GridColumn[] = [
  { key: "a", width: 72 },
  { key: "b", width: 360 },
  { key: "c", width: 132, align: "right" },
  { key: "d", width: 132, align: "right" },
];

/** Workbook cells read as the file has them: two decimals, no symbol. */
const cell = (v: string): string => (v === "" ? "" : amount(v, "cents").text);

const TB_ROWS: readonly GridRow[] = [
  { id: "head", cells: { a: "Account", b: "Name", c: "Debit", d: "Credit" } },
  ...NORTHWIND_TB.map(([code, name, debit, credit]) => ({
    id: code,
    cells: { a: code, b: name, c: cell(debit), d: cell(credit) },
  })),
];

export function GridSpecimen(): JSX.Element {
  return (
    <Sheet title="Grid grammar" meta="letters 26 · row numbers 34 · td 27 · hair right and bottom">
      <Row name="Workbook" meaning="Header row in espresso; D9 cited; a comment on C9">
        <div className="w-[760px]">
          <GridTable
            label={TB_FILE}
            source={TB_FILE}
            sheet={TB_SHEET}
            columns={TB_COLUMNS}
            rows={TB_ROWS}
            headerRow
            cite="C9"
            comments={{
              C9: {
                by: STAFF.hannah,
                text: "Agrees to the Keystone loan roll-forward balance at December 31, 2025.",
              },
            }}
          />
        </div>
      </Row>
      <Row name="Range" meaning="A cited range lights every row in it: B6:C7">
        <div className="w-[760px]">
          <GridTable
            label={`${TB_FILE}, range`}
            columns={TB_COLUMNS}
            rows={TB_ROWS.slice(0, 8)}
            headerRow
            cite={`${TB_SHEET}!B6:C7`}
            resizable={false}
          />
        </div>
      </Row>
    </Sheet>
  );
}

export function LeadsheetSpecimen(): JSX.Element {
  // Line 1a is lit as the W-2 is open; hovering a source box lights its line (E1).
  return (
    <Sheet title="Leadsheet grammar" meta="no header · rows 9 14 at 13 · whole dollars · line 52">
      <MatchScope>
        <PinOnMount id={feldBox("w2:1")} />
        <div data-artboard="c-01-leadsheet" className="w-[560px]">
          <EvidenceTable
            label="Feld 2025 Form 1040 leadsheet"
            grammar="leadsheet"
            blocks={FELD_LEADSHEETS.map((b) => ({ ...b, columns: LEADSHEET_COLUMNS }))}
            rowMatch={leadsheetMatch}
          />
        </div>
        <Row name="Source boxes" meaning="Hover one: its leadsheet line lights">
          {[
            ["w2:1", "W-2 box 1"],
            ["1099:int-1", "1099-INT box 1"],
            ["1099:div-1a", "1099-DIV box 1a"],
          ].map(([key, name]) => (
            <Matchable
              key={key}
              id={feldBox(key ?? "")}
              className="rounded-value bg-nested px-[6px] py-[2px] text-meta text-ink-2"
            >
              {name}
            </Matchable>
          ))}
        </Row>
      </MatchScope>
    </Sheet>
  );
}

/** Pins a match once the scope is up: the document open beside the sheet. */
function PinOnMount({ id }: { id: MatchId }): null {
  const store = useMatchStore();
  useEffect(() => {
    if (store.get().id !== id) store.togglePin(id, null);
  }, [store, id]);
  return null;
}

export function FieldRowsSpecimen(): JSX.Element {
  const [flags, setFlags] = useState<readonly string[]>([]);
  const [wages, interest] = feldWorksheets();
  const [, mismatched] = feldWorksheets(true);
  return (
    <Sheet title="Field rows" meta="min 42 · value box 96 to 140 · Flag and Info on hover">
      <MatchScope>
        <div data-artboard="c-01-fields" className="flex w-[560px] flex-col">
          {wages !== undefined && (
            <FieldBlock
              title={wages.title}
              meta={wages.meta}
              rows={wages.rows.map((r, i) => (i === 0 ? { ...r, matched: true } : r))}
              onFlag={(row, on) => {
                setFlags((f) => (on ? [...f, row.label] : f.filter((x) => x !== row.label)));
              }}
            />
          )}
          {interest !== undefined && (
            <FieldBlock title={interest.title} meta={interest.meta} rows={interest.rows} />
          )}
        </div>
        <Row name="Flagged" meaning="onFlag reports the row">
          <span data-fields="flags" className="text-dense text-ink-2">
            {flags.length === 0 ? "None flagged" : flags.join(", ")}
          </span>
        </Row>
      </MatchScope>
      <Row name="States" meaning="mismatch, hover, Info open">
        {mismatched !== undefined && (
          <Held name="mismatch: red ink, Flag on">
            <FieldBlock
              className="w-[520px]"
              title={mismatched.title}
              rows={mismatched.rows.filter((r) => r.id === "ws-3b")}
            />
          </Held>
        )}
        {interest !== undefined && (
          <Held name="hover">
            <FieldBlock
              className="w-[520px]"
              title={interest.title}
              rows={interest.rows.slice(0, 1)}
              forceState={{ row: "ws-2b", state: "hover" }}
            />
          </Held>
        )}
        {interest !== undefined && (
          <Held name="Info open">
            <FieldBlock
              className="w-[520px] pb-[96px]"
              title={interest.title}
              rows={interest.rows.slice(1, 2)}
              forceState={{ row: "ws-3a", state: "open" }}
            />
          </Held>
        )}
      </Row>
    </Sheet>
  );
}

// ---- 1,000 fixture rows -------------------------------------------------------------------------

const LOAD_COLUMNS: readonly TableColumn[] = [
  { key: "item", header: "Account", type: "label" },
  { key: "debit", header: "Debit", width: 150 },
  { key: "credit", header: "Credit", width: 150 },
];

/** 40 bands of 24 lines: the seed's trial balance lines over and over, 1,000 rows in all. A load
 * fixture for the virtualiser, not a ledger anyone keeps. */
export const LOAD_ROWS: readonly TableRow[] = Array.from({ length: 40 }, (_, b) => [
  {
    id: `band-${String(b + 1)}`,
    kind: "group" as const,
    label: `Batch ${String(b + 1)}`,
    cells: {},
  },
  ...Array.from({ length: 24 }, (_, i) => {
    const line = NORTHWIND_TB[i % NORTHWIND_TB.length] ?? NORTHWIND_TB[0];
    const [code, name, debit, credit] = line ?? ["", "", "", ""];
    return {
      id: `b${String(b + 1)}-${String(i + 1)}`,
      label: `${code} ${name}`,
      cells: {
        debit: { value: debit === "" ? null : debit },
        credit: { value: credit === "" ? null : credit },
      },
    };
  }),
]).flat();

export function VirtualGridSpecimen(): JSX.Element {
  return (
    <Sheet
      title="Virtualisation"
      meta={`${String(LOAD_ROWS.length)} fixture rows · sticky header and bands`}
    >
      <div data-artboard="c-01-virtual" className="w-[760px]">
        <DataGrid
          label={`${NORTHWIND_PLAN} trial balance, 1,000 fixture rows`}
          columns={LOAD_COLUMNS}
          rows={LOAD_ROWS}
          maxHeight={420}
        />
      </div>
    </Sheet>
  );
}

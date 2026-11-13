// TXP-02 on the live client (T-05-T37): the trial balance and its tallies for the view and the
// statement, Building while a workbook run imports the trial balance (the newest run running).
// T-05-T37 rest (DEC-4629): the overlays. A row opens SHL-09 on its sheet 01 cells (a2), an
// entry's reference opens its drawer (a3), "Map…" opens the line picker (e2) whose pick the server
// answers as mapped (the tax reviewer) or proposed (anyone else).
import type { WorkbookJournalEntryOut } from "@abacus/api-client";
import {
  entityFormLinesOptions,
  entityJournalEntriesOptions,
  entityMappingMutation,
  entityRunsOptions,
  entityTalliesOptions,
  entityTrialBalanceOptions,
} from "@abacus/api-client/query";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { TXP02, type Txp02Statement, type Txp02View } from "./index";
import { type CellTarget, CellDrawer, EntryDrawer, LinePicker } from "./Overlays";

/** The return's form code to the form-line set's (`GET /v1/form-lines?form=`). */
const PICKER_FORM: Readonly<Record<string, "1065" | "1120-S" | "1120" | "990">> = {
  "1065": "1065",
  "1120s": "1120-S",
  "1120": "1120",
  "990": "990",
};

export function Financials({
  returnId,
  form,
  taxYear,
}: {
  returnId: string;
  /** The return's form and tax year: the line picker's published set. */
  form: string;
  taxYear: number;
}): JSX.Element {
  const setForm = PICKER_FORM[form];
  const [view, setView] = useState<Txp02View>("account");
  const [statement, setStatement] = useState<Txp02Statement>("full");
  const [unmappedOnly, setUnmappedOnly] = useState(false);
  const [cell, setCell] = useState<CellTarget | null>(null);
  const [entry, setEntry] = useState<WorkbookJournalEntryOut | null>(null);
  const [picking, setPicking] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const path = { return_id: returnId };
  const client = useQueryClient();
  const tb = useQuery(
    entityTrialBalanceOptions({
      path,
      query: { view, statement, ...(unmappedOnly ? { filter: "unmapped" as const } : {}) },
    }),
  );
  const tallies = useQuery(entityTalliesOptions({ path }));
  const runs = useQuery(entityRunsOptions({ path }));
  const entries = useQuery(entityJournalEntriesOptions({ path }));
  const lines = useQuery({
    ...entityFormLinesOptions({
      query: {
        form: setForm ?? "1065",
        tax_year: taxYear,
        ...(query.trim() === "" ? {} : { q: query.trim() }),
      },
    }),
    enabled: picking !== null && setForm !== undefined,
  });
  const pick = useMutation({
    ...entityMappingMutation(),
    onSuccess: (out) => {
      if (out.state === "mapped") void client.invalidateQueries();
    },
  });
  const building = runs.data?.items[0]?.state === "running";
  return (
    <>
      <TXP02
        tb={tb.data}
        tallies={tallies.data}
        view={view}
        statement={statement}
        building={building}
        onView={setView}
        onStatement={setStatement}
        onUnmapped={() => {
          setUnmappedOnly((on) => !on);
        }}
        onMap={(code) => {
          pick.reset();
          setQuery("");
          setPicking(code);
        }}
        onOpenRow={(code) => {
          const row = tb.data?.rows.find((r) => r.account_code === code);
          if (row === undefined) return;
          setCell({
            returnId,
            accountCode: row.account_code,
            accountName: row.account_name,
            cells: row.cells ?? {},
          });
        }}
        entries={entries.data?.items}
        onOpenEntry={setEntry}
      />
      <CellDrawer
        target={cell}
        onClose={() => {
          setCell(null);
        }}
      />
      <EntryDrawer
        entry={entry}
        onClose={() => {
          setEntry(null);
        }}
      />
      <LinePicker
        accountCode={picking}
        lines={lines.data?.items ?? []}
        query={query}
        onQuery={setQuery}
        busy={pick.isPending}
        outcome={pick.data?.state}
        onPick={(key) => {
          if (picking === null) return;
          pick.mutate({
            path,
            body: { account_code: picking, form_line_key: key },
            headers: { "Idempotency-Key": `${returnId}:${picking}:${key}` },
          });
        }}
        onClose={() => {
          setPicking(null);
        }}
      />
    </>
  );
}

// TXP-11 on the live client (T-05-T38): the selected sheet's cells, and a person's edit through
// PUT …/workbook/cells/{sheet!A1} with the cell's version; 409 `cell_version_conflict` shows the
// conflict line and Reload refetches. The server recomputes dependents and checkpoints the edit
// (T-05-T35); the screen only re-reads.
// T-05-T38 rest (DEC-4630): the version picker reads an earlier run's workbook read-only
// (`?version=`); the selected cell opens SHL-09 (a3) and its citations (SHL-07, a2), a document
// citation opening SHL-08 at its match (d).
import type { CitationV2Out } from "@abacus/api-client";
import {
  entityEditCellMutation,
  entitySheetOptions,
  workbookOptions,
} from "@abacus/api-client/query";
import { useMutation, useQuery } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { ViewerDrawer } from "../SHL-08";
import { TXP11, type Txp11Sheet, keyOf } from "./index";
import { CitationsDrawer, ProvenanceDrawer } from "./Overlays";

export function Workpaper({
  returnId,
  initial = "H12",
}: {
  returnId: string;
  /** The cell an issue opened (TXP-10 → `?cell=`), H12 by default (A). */
  initial?: string;
}): JSX.Element {
  const [sheet, setSheet] = useState<Txp11Sheet>("05 Capital");
  const [selected, setSelected] = useState(initial);
  const [conflict, setConflict] = useState(false);
  const [version, setVersion] = useState<number | undefined>(undefined);
  const [provenanceOf, setProvenanceOf] = useState<string | null>(null);
  const [citationsOf, setCitationsOf] = useState<string | null>(null);
  const [source, setSource] = useState<CitationV2Out | null>(null);
  const key = keyOf(sheet);
  const book = useQuery(workbookOptions({ path: { return_id: returnId } }));
  const versions = (book.data?.versions ?? []).map((v) => v.version);
  const newest = versions[0];
  const past = version !== undefined && newest !== undefined && version !== newest;
  const cells = useQuery(
    entitySheetOptions({
      path: { return_id: returnId, sheet: key },
      ...(past ? { query: { version } } : {}),
    }),
  );
  const edit = useMutation(entityEditCellMutation());
  const versionOf = (address: string): number =>
    cells.data?.cells.find((c) => c.address === address)?.version ?? 0;
  const citationIds =
    cells.data?.cells.find((c) => `${key}!${c.address}` === citationsOf)?.citation_ids ?? [];
  const evidence = source?.source.evidence_version_id ?? null;
  return (
    <>
      <TXP11
        sheet={sheet}
        data={cells.data}
        selected={selected}
        conflict={conflict}
        saving={edit.isPending}
        readOnly={past}
        versions={versions}
        version={version ?? newest}
        onVersion={setVersion}
        onProvenance={(address) => {
          setProvenanceOf(`${key}!${address}`);
        }}
        onCitations={(address) => {
          setCitationsOf(`${key}!${address}`);
        }}
        onSelect={setSelected}
        onSheet={(next) => {
          setSheet(next);
          setSelected("A1");
        }}
        onReload={() => {
          setConflict(false);
          void cells.refetch();
        }}
        {...(past
          ? {}
          : {
              onCommit: (address: string, value: string) => {
                const isFormula = value.trim().startsWith("=");
                edit.mutate(
                  {
                    path: { return_id: returnId, address: `${key}!${address}` },
                    headers: { "Idempotency-Key": crypto.randomUUID() },
                    body: {
                      expected_version: versionOf(address),
                      ...(isFormula ? { formula: value } : { value }),
                    },
                  },
                  {
                    onSuccess: () => {
                      void cells.refetch();
                    },
                    onError: (error: unknown) => {
                      // The API's error body names its code in `detail` (C2 errors).
                      const detail = (error as { detail?: unknown } | null)?.detail;
                      if (detail === "cell_version_conflict") setConflict(true);
                    },
                  },
                );
              },
            })}
      />
      <ProvenanceDrawer
        returnId={returnId}
        address={provenanceOf}
        onClose={() => {
          setProvenanceOf(null);
        }}
      />
      <CitationsDrawer
        address={citationsOf}
        citationIds={citationIds}
        onClose={() => {
          setCitationsOf(null);
        }}
        onOpenSource={setSource}
      />
      {evidence === null ? null : (
        <ViewerDrawer
          target={{ versionId: evidence, matchId: source?.match_id ?? null }}
          open
          onOpenChange={(open) => {
            if (!open) setSource(null);
          }}
        />
      )}
    </>
  );
}

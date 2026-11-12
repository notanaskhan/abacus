// TXP-11 on the live client (T-05-T38): the selected sheet's cells, and a person's edit through
// PUT …/workbook/cells/{sheet!A1} with the cell's version; 409 `cell_version_conflict` shows the
// conflict line and Reload refetches. The server recomputes dependents and checkpoints the edit
// (T-05-T35); the screen only re-reads.
import { entityEditCellMutation, entitySheetOptions } from "@abacus/api-client/query";
import { useMutation, useQuery } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { TXP11, type Txp11Sheet, keyOf } from "./index";

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
  const key = keyOf(sheet);
  const cells = useQuery(entitySheetOptions({ path: { return_id: returnId, sheet: key } }));
  const edit = useMutation(entityEditCellMutation());
  const versionOf = (address: string): number =>
    cells.data?.cells.find((c) => c.address === address)?.version ?? 0;
  return (
    <TXP11
      sheet={sheet}
      data={cells.data}
      selected={selected}
      conflict={conflict}
      saving={edit.isPending}
      onSelect={setSelected}
      onSheet={(next) => {
        setSheet(next);
        setSelected("A1");
      }}
      onReload={() => {
        setConflict(false);
        void cells.refetch();
      }}
      onCommit={(address, value) => {
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
      }}
    />
  );
}

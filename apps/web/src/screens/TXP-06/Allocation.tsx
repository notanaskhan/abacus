// TXP-06 on the live client (T-05-T44): the structure, a live preview while a rung is edited (no
// persistence until Save, which PUTs a new draft version with `expected_version`), and the
// partner series. Approve structure hands the pending version to the host's SHL-12 at L3 (the
// shell's sign-off overlay calls `POST …/allocation-structure/approve`).
import type {
  WorkbookAllocationDraftIn,
  WorkbookAllocationStructureOut,
} from "@abacus/api-client";
import {
  entityAllocationDraftMutation,
  entityAllocationOptions,
  entityAllocationPreviewMutation,
} from "@abacus/api-client/query";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { TXP06 } from "./index";

function draftOf(
  s: WorkbookAllocationStructureOut,
  edits: Readonly<Record<number, string>>,
): WorkbookAllocationDraftIn {
  return {
    expected_version: s.latest_version ?? s.version,
    kind: s.kind,
    method: s.method ?? "interim_closing",
    convention: s.convention ?? "calendar_day",
    income: s.income ?? null,
    rungs: s.rungs.map((r, i) => ({
      ...r,
      percentage: edits[i + 1] ?? r.percentage ?? null,
    })),
  };
}

export function Allocation({
  returnId,
  onClose,
  onSignOff,
  onCitation,
  onItemL,
}: {
  returnId: string;
  onClose: () => void;
  /** C → C2: SHL-12 at L3 on the pending version (the host's overlay). */
  onSignOff?: (structure: WorkbookAllocationStructureOut) => void;
  onCitation?: (citationId: string) => void;
  onItemL?: () => void;
}): JSX.Element {
  const path = { return_id: returnId };
  const client = useQueryClient();
  const structure = useQuery(entityAllocationOptions({ path }));
  const preview = useMutation(entityAllocationPreviewMutation());
  const save = useMutation({
    ...entityAllocationDraftMutation(),
    onSuccess: () =>
      void client.invalidateQueries({ queryKey: entityAllocationOptions({ path }).queryKey }),
  });
  const [selected, setSelected] = useState<string | null>(null);
  const [editing, setEditing] = useState<number | null>(null);
  const [edits, setEdits] = useState<Readonly<Record<number, string>>>({});
  const s = structure.data;
  return (
    <TXP06
      structure={s}
      preview={editing === null ? undefined : preview.data}
      selected={selected}
      editing={editing}
      onClose={onClose}
      onSelect={setSelected}
      onEdit={(priority) => {
        setEditing(priority);
        if (priority === null) setEdits({});
      }}
      onRung={(priority, value) => {
        if (s === undefined) return;
        const next = { ...edits, [priority]: value };
        setEdits(next);
        preview.mutate({ path, body: draftOf(s, next) });
      }}
      onSave={() => {
        if (s === undefined) return;
        save.mutate(
          { path, body: draftOf(s, edits), headers: { "Idempotency-Key": crypto.randomUUID() } },
          {
            onSuccess: () => {
              setEditing(null);
              setEdits({});
            },
          },
        );
      }}
      {...(s !== undefined && onSignOff !== undefined
        ? {
            onApprove: () => {
              onSignOff(s);
            },
          }
        : {})}
      {...(onCitation === undefined ? {} : { onCitation })}
      {...(onItemL === undefined ? {} : { onItemL })}
    />
  );
}

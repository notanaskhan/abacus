// TXP-06 on the live client (T-05-T44): the structure, a live preview while a rung is edited (no
// persistence until Save, which PUTs a new draft version with `expected_version`), and the
// partner series. Approve structure opens SHL-12 at L3 on the pending version; the sheet signs
// through `POST …/allocation-structure/approve` (not P-04's bare write), so the L3 also writes the
// approved version and starts the capital and K-1 re-run (S41 leftover, DEC-4736).
import {
  type WorkbookAllocationDraftIn,
  type WorkbookAllocationStructureOut,
  signOffLadder,
} from "@abacus/api-client";
import {
  entityAllocationApproveMutation,
  entityAllocationDraftMutation,
  entityAllocationOptions,
  entityAllocationPreviewMutation,
  entityRunsOptions,
} from "@abacus/api-client/query";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import type { SignOffWriter } from "../../domain/review";
import { SignOffSheet } from "../SHL-12";
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
  /** C → C2: SHL-12 at L3 on the pending version. Without it, this host opens the sheet itself. */
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
  const [approving, setApproving] = useState<string | null>(null);
  const approve = useMutation(entityAllocationApproveMutation());
  const s = structure.data;
  // The approve route records P-04's L3 and answers its id; the sheet's toast and `onSigned` read
  // the sign-off itself, which the target's ladder carries.
  const write: SignOffWriter = async (e) => {
    const done = await approve.mutateAsync({
      path,
      body: { seen_hash: e.target.content_hash, statement_version: e.statement.version },
      headers: { "Idempotency-Key": crypto.randomUUID() },
    });
    const { data: ladder } = await signOffLadder({
      query: { target_type: e.target.target_type, target_id: e.target.target_id },
      throwOnError: true,
    });
    const signed = ladder.levels.find((l) => l.latest?.id === done.sign_off_id)?.latest;
    if (signed == null) throw new Error("sign_off_not_found");
    return signed;
  };
  const sign =
    onSignOff ??
    ((next: WorkbookAllocationStructureOut) => {
      if (next.sign_off_target_id != null) setApproving(next.sign_off_target_id);
    });
  return (
    <>
      {approving === null ? null : (
        <SignOffSheet
          target={{ type: "allocation_structure", id: approving }}
          level="L3"
          open
          onOpenChange={(next) => {
            if (!next) setApproving(null);
          }}
          write={write}
          onSigned={() => {
            void client.invalidateQueries({
              queryKey: entityAllocationOptions({ path }).queryKey,
            });
            void client.invalidateQueries({ queryKey: entityRunsOptions({ path }).queryKey });
          }}
        />
      )}
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
        {...(s !== undefined && s.status === "pending_approval"
          ? {
              onApprove: () => {
                sign(s);
              },
            }
          : {})}
        {...(onCitation === undefined ? {} : { onCitation })}
        {...(onItemL === undefined ? {} : { onItemL })}
      />
    </>
  );
}

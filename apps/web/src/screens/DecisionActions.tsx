import {
  acceptMutation,
  reasonCodesOptions,
  rejectMutation,
  sendBackMutation,
} from "@abacus/api-client/query";
import { Alert, Button, Input, Label } from "@abacus/ui";
import { useMutation, useQuery } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { errorMessage } from "../api";

type Kind = "accept" | "reject" | "send_back";
export const KIND_LABEL: Record<Kind, string> = {
  accept: "Accept",
  reject: "Reject",
  send_back: "Send back",
};

/** Accept, reject or send back one evidence version (SPEC-004; shared by the review queue and
 * the item page, SPEC-021 AC-4). The API decides who may; a decision is final, so ask once. */
export function DecisionActions({
  engagementId,
  versionId,
  itemLabel,
  seenProposal,
  onSettled,
}: {
  engagementId: string;
  versionId: string;
  itemLabel: string;
  seenProposal: string | null;
  onSettled: () => void;
}): JSX.Element {
  const after = { onSuccess: onSettled, onError: onSettled };
  const accept = useMutation({ ...acceptMutation(), ...after });
  const reject = useMutation({ ...rejectMutation(), ...after });
  const sendBack = useMutation({ ...sendBackMutation(), ...after });
  const [kind, setKind] = useState<Kind>("accept");
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const codes = useQuery({
    ...reasonCodesOptions({
      path: {
        engagement_id: engagementId,
        applies_to: kind === "send_back" ? "send_back" : "reject",
      },
    }),
    enabled: kind !== "accept",
  });
  const chosen = codes.data?.find((c) => c.code === reason);
  const noteNeeded = chosen?.requires_note === true && note.trim() === "";
  const deciding = accept.isPending || reject.isPending || sendBack.isPending;
  const failed = accept.error ?? reject.error ?? sendBack.error;
  const path = { engagement_id: engagementId, version_id: versionId };
  const decide = (): void => {
    if (!window.confirm(`${KIND_LABEL[kind]} "${itemLabel}"? A decision can't be changed.`)) {
      return;
    }
    const shared = { note: note.trim() === "" ? null : note.trim(), seen_proposal: seenProposal };
    if (kind === "accept") {
      accept.mutate({ path, body: shared });
    } else if (kind === "reject") {
      reject.mutate({ path, body: { ...shared, reason_code: reason } });
    } else {
      sendBack.mutate({ path, body: { ...shared, reason_code: reason } });
    }
  };
  return (
    <>
      <fieldset className="flex flex-wrap items-end gap-3" disabled={deciding}>
        <legend className="sr-only">Decision on {itemLabel}</legend>
        <Label className="flex flex-col gap-1">
          Decision
          <select
            className="rounded border px-2 py-1"
            value={kind}
            onChange={(e) => {
              setKind(e.target.value as Kind);
              setReason("");
            }}
          >
            <option value="accept">Accept</option>
            <option value="reject">Reject</option>
            <option value="send_back">Send back</option>
          </select>
        </Label>
        {kind !== "accept" && (
          <Label className="flex flex-col gap-1">
            Reason (required)
            <select
              className="rounded border px-2 py-1"
              value={reason}
              onChange={(e) => {
                setReason(e.target.value);
              }}
            >
              <option value="">Choose a reason</option>
              {(codes.data ?? []).map((c) => (
                <option key={c.code} value={c.code}>
                  {c.label}
                </option>
              ))}
            </select>
          </Label>
        )}
        <Label className="flex flex-col gap-1">
          {chosen?.requires_note === true ? "Note (required)" : "Note"}
          <Input
            value={note}
            maxLength={2000}
            onChange={(e) => {
              setNote(e.target.value);
            }}
          />
        </Label>
        <Button
          size="sm"
          aria-label={`${KIND_LABEL[kind]} ${itemLabel}`}
          onClick={decide}
          disabled={(kind !== "accept" && reason === "") || noteNeeded}
        >
          {KIND_LABEL[kind]}
        </Button>
      </fieldset>
      {kind !== "accept" && codes.isError && (
        <Alert title="Couldn't load the reason codes">{errorMessage(codes.error)}</Alert>
      )}
      {failed !== null && <Alert title="That didn't work">{errorMessage(failed)}</Alert>}
    </>
  );
}

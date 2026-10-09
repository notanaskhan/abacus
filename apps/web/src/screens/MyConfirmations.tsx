import {
  independenceMutation,
  myConfirmationsOptions,
  myConfirmationsQueryKey,
} from "@abacus/api-client/query";
import { Button, Input, Panel, StatusPill } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { errorMessage } from "../api";

/** SPEC-025 AC-5: the person's own independence confirmations still to give. */
export function MyConfirmations(): JSX.Element | null {
  const open = useQuery({ ...myConfirmationsOptions(), retry: false });
  if (open.data === undefined || open.data.length === 0) return null;
  return (
    <Panel title="Your independence confirmations">
      <ul className="flex flex-col divide-y divide-line">
        {open.data.map((c) => (
          <ConfirmationRow
            key={c.engagement_id}
            engagementId={c.engagement_id}
            label={`${c.client_name} · ${c.engagement_name}`}
            statement={c.statement}
            declined={c.status === "declined"}
          />
        ))}
      </ul>
    </Panel>
  );
}

/** SPEC-025 AC-7 (TASK-045): on an engagement, until the person confirms, client data stays
 * closed to them; say so and let them answer here. */
export function IndependenceBanner({
  engagementId,
}: {
  engagementId: string;
}): JSX.Element | null {
  const open = useQuery({ ...myConfirmationsOptions(), retry: false });
  const mine = open.data?.find((c) => c.engagement_id === engagementId);
  if (mine === undefined) return null;
  return (
    <Panel
      role="status"
      title="Confirm your independence to see client data"
      action={<StatusPill tone="warning">Client data closed to you</StatusPill>}
    >
      <ul>
        <ConfirmationRow
          engagementId={engagementId}
          label={`${mine.client_name} · ${mine.engagement_name}`}
          statement={mine.statement}
          declined={mine.status === "declined"}
        />
      </ul>
    </Panel>
  );
}

function ConfirmationRow({
  engagementId,
  label,
  statement,
  declined,
}: {
  engagementId: string;
  label: string;
  statement: string;
  declined: boolean;
}): JSX.Element {
  const queryClient = useQueryClient();
  const [declining, setDeclining] = useState(false);
  const [note, setNote] = useState("");
  const answer = useMutation({
    ...independenceMutation(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: myConfirmationsQueryKey() });
      // Client data may have opened (TASK-045): refetch what this engagement's tabs show.
      void queryClient.invalidateQueries();
    },
  });
  const send = (confirm: boolean): void => {
    answer.mutate({
      path: { engagement_id: engagementId },
      body: confirm ? { confirm: true } : { confirm: false, note },
    });
  };
  return (
    <li className="flex flex-col gap-2 py-3 text-sm">
      <p className="font-medium">{label}</p>
      <p className="text-muted">{statement}</p>
      {declined && (
        <p className="text-xs text-danger">You declined. Confirm if that has changed.</p>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <Button
          size="sm"
          disabled={answer.isPending}
          onClick={() => {
            send(true);
          }}
        >
          Confirm
        </Button>
        {!declining ? (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setDeclining(true);
            }}
          >
            I can&apos;t confirm
          </Button>
        ) : (
          <>
            <Input
              aria-label={`Why you can't confirm for ${label}`}
              maxLength={1000}
              placeholder="For the engagement partner"
              value={note}
              onChange={(e) => {
                setNote(e.target.value);
              }}
            />
            <Button
              size="sm"
              variant="danger"
              disabled={note.trim() === "" || answer.isPending}
              onClick={() => {
                send(false);
              }}
            >
              Decline
            </Button>
          </>
        )}
      </div>
      {answer.isError && (
        <p role="alert" className="text-danger">
          {errorMessage(answer.error)}
        </p>
      )}
    </li>
  );
}

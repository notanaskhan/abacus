import { acknowledgeStepMutation, onboardingQueryKey } from "@abacus/api-client/query";
import { Button } from "@abacus/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { ConfirmItsYou, isForbidden } from "../shell/mfa";

/** SPEC-024 AC-7: confirm a checklist step from its own screen ("Looks right", "None needed"). */
export function AcknowledgeStep({
  step,
  label,
}: {
  step: "budget" | "walls";
  label: string;
}): JSX.Element {
  const queryClient = useQueryClient();
  const [confirm, setConfirm] = useState(false);
  const ack = useMutation({
    ...acknowledgeStepMutation(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: onboardingQueryKey() });
    },
    onError: (error) => {
      if (isForbidden(error)) setConfirm(true);
    },
  });
  return (
    <>
      <Button
        size="sm"
        variant="ghost"
        disabled={ack.isPending || ack.isSuccess}
        onClick={() => {
          ack.mutate({ path: { step } });
        }}
      >
        {ack.isSuccess ? "Noted" : label}
      </Button>
      <ConfirmItsYou open={confirm} onOpenChange={setConfirm} />
    </>
  );
}

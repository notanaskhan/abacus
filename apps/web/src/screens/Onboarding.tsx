import type { StepOut } from "@abacus/api-client";
import {
  acknowledgeStepMutation,
  dismissOnboardingMutation,
  onboardingOptions,
  onboardingQueryKey,
} from "@abacus/api-client/query";
import { Button, Panel, StatusPill } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { type JSX, useState } from "react";
import { errorMessage } from "../api";
import { ConfirmItsYou, isForbidden } from "../shell/mfa";

type StepCopy = { title: string; detail: string; to: string; action: string };

// SPEC-024 AC-7: the steps from sign-up to the first engagement.
const STEPS: Record<StepOut["id"], StepCopy> = {
  sso: {
    title: "Connect single sign-on",
    detail:
      "Coming soon. Your team signs in with email and multi-factor authentication until then.",
    to: "/admin/people",
    action: "",
  },
  team: {
    title: "Invite your team",
    detail: "Give each person a role.",
    to: "/admin/people",
    action: "Invite people",
  },
  methodology: {
    title: "Upload your methodology",
    detail: "Templates, audit areas and account rules, checked row by row.",
    to: "/admin/methodology",
    action: "Upload",
  },
  autonomy: {
    title: "Set autonomy",
    detail: "Choose what the agent may do on its own. Firms start at Routine.",
    to: "/admin/autonomy",
    action: "Choose",
  },
  budget: {
    title: "Review your AI budget",
    detail: "Monthly limits for model spend.",
    to: "/admin/budget",
    action: "Review",
  },
  walls: {
    title: "Add ethical walls",
    detail: "Keep specific people away from specific clients, or confirm none are needed.",
    to: "/admin/walls",
    action: "Review",
  },
  engagement: {
    title: "Create your first engagement",
    detail: "Then import or apply your request list.",
    to: "/",
    action: "",
  },
};

/** SPEC-024 AC-7: shown to firm administrators until every step is done or it's dismissed. */
export function Onboarding({ always = false }: { always?: boolean }): JSX.Element | null {
  const queryClient = useQueryClient();
  const state = useQuery({ ...onboardingOptions(), retry: false });
  const [confirm, setConfirm] = useState(false);
  const after = {
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: onboardingQueryKey() });
    },
    onError: (error: unknown) => {
      if (isForbidden(error)) setConfirm(true);
    },
  };
  const acknowledge = useMutation({ ...acknowledgeStepMutation(), ...after });
  const dismiss = useMutation({ ...dismissOnboardingMutation(), ...after });
  if (state.data === undefined) return null; // not a firm administrator, or still loading
  const { steps, complete, dismissed } = state.data;
  if (!always && (complete || dismissed)) return null;
  const done = steps.filter((s) => s.done).length;
  const failure = [acknowledge, dismiss].find((m) => m.isError && !isForbidden(m.error));
  return (
    <Panel
      title="Get your firm ready"
      action={
        <span className="flex items-center gap-2">
          <StatusPill tone={complete ? "success" : "info"}>
            {`${String(done)} of ${String(steps.length)} done`}
          </StatusPill>
          {!complete && !always && (
            <Button
              size="sm"
              variant="ghost"
              disabled={dismiss.isPending}
              onClick={() => {
                dismiss.mutate({});
              }}
            >
              Dismiss
            </Button>
          )}
        </span>
      }
    >
      <ol aria-label="Setup steps" className="flex flex-col divide-y divide-line">
        {steps.map((step, index) => {
          const copy = STEPS[step.id];
          return (
            <li key={step.id} className="flex flex-wrap items-center justify-between gap-3 py-2">
              <div className="flex items-start gap-3">
                <span
                  aria-hidden="true"
                  className={`mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
                    step.done ? "bg-ok-soft text-ok" : "bg-sunken text-muted"
                  }`}
                >
                  {step.done ? "✓" : String(index + 1)}
                </span>
                <div>
                  <p className="font-medium">
                    {copy.title}
                    <span className="sr-only">{step.done ? " (done)" : " (to do)"}</span>
                  </p>
                  <p className="text-sm text-muted">
                    {step.how === "skipped"
                      ? "Skipped for now."
                      : step.how === "none_needed"
                        ? "No walls needed."
                        : copy.detail}
                  </p>
                </div>
              </div>
              {!step.done && (
                <span className="flex gap-2">
                  {step.id === "sso" && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        acknowledge.mutate({ path: { step: "sso" } });
                      }}
                    >
                      Skip for now
                    </Button>
                  )}
                  {copy.action !== "" && (
                    <Link
                      to={copy.to}
                      className="text-sm font-semibold text-accent hover:underline"
                    >
                      {copy.action}
                    </Link>
                  )}
                </span>
              )}
            </li>
          );
        })}
      </ol>
      {failure !== undefined && (
        <p role="alert" className="text-sm text-danger">
          {errorMessage(failure.error)}
        </p>
      )}
      <ConfirmItsYou open={confirm} onOpenChange={setConfirm} />
    </Panel>
  );
}

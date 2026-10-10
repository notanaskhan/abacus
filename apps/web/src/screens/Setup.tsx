import type { SetupStepOut } from "@abacus/api-client";
import { meOptions, setupOptions, teamOptions } from "@abacus/api-client/query";
import { Alert, Panel, Skeleton, StatusPill } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { Link, Navigate } from "@tanstack/react-router";
import type { JSX } from "react";
import { errorMessage } from "../api";
import { isForbidden } from "../shell/mfa";
import { EngagementRecords } from "./EngagementRecords";
import { ReminderDrafts } from "./ReminderDrafts";

type Tone = "success" | "info" | "warning" | "danger" | "neutral";
const STATE: Record<SetupStepOut["state"], { tone: Tone; label: string }> = {
  done: { tone: "success", label: "Done" },
  waiting: { tone: "info", label: "Waiting" },
  blocked: { tone: "danger", label: "Blocked" },
  warning: { tone: "warning", label: "Needs attention" },
  not_needed: { tone: "neutral", label: "Not needed" },
};
// Where each step is done (TASK-046): the records' panels are on this page.
const WHERE: Partial<Record<SetupStepOut["key"], "people" | "overview">> = {
  team: "people",
  client_contacts: "people",
  request_list: "overview",
};

/** SPEC-025 AC-10: where the engagement's setup stands — a summary, the checklist with who acts
 * next and why anything is blocked, then the acceptance, independence and letter records. */
export function Setup({ engagementId }: { engagementId: string }): JSX.Element {
  const setup = useQuery({
    ...setupOptions({ path: { engagement_id: engagementId } }),
    retry: false,
  });
  if (setup.isPending) return <Skeleton className="h-64" />;
  if (setup.isError) {
    return isForbidden(setup.error) ? (
      <Alert title="Not available">
        The engagement&apos;s setup is for its team and the firm&apos;s administrators.
      </Alert>
    ) : (
      <Alert title="Couldn't load the setup">{errorMessage(setup.error)}</Alert>
    );
  }
  return (
    <div className="flex flex-col gap-6">
      <p className="text-base">{setup.data.summary}</p>
      <Panel title="Setup checklist">
        <ol className="flex flex-col divide-y divide-line">
          {setup.data.steps.map((step) => (
            <StepRow key={step.key} step={step} engagementId={engagementId} />
          ))}
        </ol>
      </Panel>
      <ReminderDrafts engagementId={engagementId} />
      <RecordsForMe engagementId={engagementId} />
    </div>
  );
}

function StepRow({
  step,
  engagementId,
}: {
  step: SetupStepOut;
  engagementId: string;
}): JSX.Element {
  const state = STATE[step.state];
  const where = WHERE[step.key];
  return (
    <li className="flex flex-col gap-1 py-3 text-sm sm:flex-row sm:items-start sm:gap-4">
      <div className="w-56 shrink-0 font-medium">{step.label}</div>
      <div className="flex flex-1 flex-col gap-1">
        <div className="flex flex-wrap items-center gap-2">
          <StatusPill tone={state.tone}>{state.label}</StatusPill>
          {step.detail != null && <span className="text-muted">{step.detail}</span>}
        </div>
        {step.reason != null && <p className="text-ink">{step.reason}</p>}
        {step.next != null && step.state !== "done" && (
          <p className="text-xs text-muted">Next: {step.next}</p>
        )}
      </div>
      {where !== undefined && step.state !== "done" && (
        <Link
          to={
            where === "people" ? "/engagements/$engagementId/people" : "/engagements/$engagementId"
          }
          params={{ engagementId }}
          className="text-sm text-accent hover:underline"
        >
          {where === "people" ? "Go to People" : "Go to Overview"}
        </Link>
      )}
    </li>
  );
}

function RecordsForMe({ engagementId }: { engagementId: string }): JSX.Element {
  const team = useQuery(teamOptions({ path: { engagement_id: engagementId } }));
  const me = useQuery(meOptions());
  const role = team.data?.find((m) => m.user_id === me.data?.user_id)?.role ?? null;
  return <EngagementRecords engagementId={engagementId} role={role} />;
}

// Engagements already sent to Setup in this page load: after that, Overview is reachable.
const sentToSetup = new Set<string>();

/** SPEC-025 (TASK-046 D2): the engagement opens on Setup until it's open for client data. */
export function DefaultToSetup({
  engagementId,
  children,
}: {
  engagementId: string;
  children: JSX.Element;
}): JSX.Element {
  const first = !sentToSetup.has(engagementId);
  const setup = useQuery({
    ...setupOptions({ path: { engagement_id: engagementId } }),
    retry: false,
    enabled: first,
  });
  if (!first) return children;
  if (setup.isPending) return <Skeleton className="h-64" />;
  sentToSetup.add(engagementId);
  if (setup.data?.blocked != null) {
    return <Navigate to="/engagements/$engagementId/setup" params={{ engagementId }} replace />;
  }
  return children;
}

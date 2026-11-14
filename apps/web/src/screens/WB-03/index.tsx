// WB-03 Run progress & review-ready results (W-02-T08 skeleton; docs/screens/WB-03.md; SPEC-653).
// The session thread at `/workbench/sessions/$sessionId`: the run arc (plan, gathering, working,
// ready for review, approved, partial failure, cancelled) is W-02-T21's, drawn from the session's
// C6 v2 items. A locked session answers with no item, so nothing of it is drawn (INV-3).
import { ErrorState, RestrictedState, WorkbenchLayout } from "@abacus/ui";
import type { JSX, ReactNode } from "react";
import { useOpenOverlay } from "../../app-core/open";
import { useWorkbenchSession } from "../../domain/workbench";
import { Thread } from "../WB-01/Thread";
import { PlanCard } from "./PlanCard";
import { hrefOf, to } from "../../routes/to";

/** WB-03's way back to the list (the thread's header, W-02-T21). */
export const SESSIONS_HREF = (): string => hrefOf(to.WB01());

export interface WB03Props {
  sessionId: string;
  list: ReactNode;
}

export function WB03({ sessionId, list }: WB03Props): JSX.Element {
  const session = useWorkbenchSession(sessionId);
  const openOverlay = useOpenOverlay();
  const body = session.isError ? (
    <ErrorState noun="this session" onRetry={() => void session.refetch()} />
  ) : session.data?.locked === true ? (
    <RestrictedState reason="walled" />
  ) : (
    // W-02-T21: the run arc on the session's thread; the plan item is the run's PlanCard.
    <div data-wb03="thread" className="flex min-h-0 flex-1 flex-col">
      <Thread
        snapshot={session.data}
        sessionId={sessionId}
        onOpenRun={(run) => {
          openOverlay({ key: "run-trace", args: [run] });
        }}
        onOpenArtifact={(id) => {
          openOverlay({ key: "artifact", args: [id] });
        }}
        planSlot={(item) =>
          item.run_id ? (
            <PlanCard
              runId={item.run_id}
              canDecide={session.data?.allowed_actions.includes("manage") === true}
            />
          ) : null
        }
      />
    </div>
  );
  return <WorkbenchLayout tab="sessions" list={list} chat={body} />;
}

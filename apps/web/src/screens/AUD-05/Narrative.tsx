import type {
  AttentionFlagOut,
  FraudSessionOut,
  WorkpaperCellOut,
  WorkpaperRecordOut,
} from "@abacus/api-client";
import {
  attentionFlagRemindMutation,
  fraudMinutesApproveMutation,
  fraudSessionOptions,
  fraudSessionQueryKey,
  workpaperRecordOptions,
} from "@abacus/api-client/query";
import {
  AgentText,
  Button,
  PaneAction,
  Pill,
  Segmented,
  ViewStateBody,
  type ViewState,
  dateTime,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { JSX } from "react";
import { useFlag } from "../../app-core/flags";
import { AuditBar, errorCode, isNotFound, useAuditCockpit } from "../../domain/audits";
import { COPY } from "./copy";

// AUD-05 · Narrative workpaper, Risk Assessment (A-04-T21; A-04 §3 AC1, AC2; the handoff spec): T2
// without the dock over `GET …/workpapers/{id}/record?tab=risk` (A-04-T04) and
// `GET …/fraud-brainstorm` (A-04-T19). The Risk tab draws the paper's sections as dark menu bands
// and its cells as KV rows; an open attention flag on a row is the amber note with Remind… and
// Escalate… (the SHL-14 draft, linked to the flag: nothing is sent). The Fraud Brainstorming tab
// shows the session, attendees, who was kept out and why, the discussion and the minutes, with
// Approve minutes only where the server allows `fraud_minutes.approve` (the engagement partner).
// Summary and Linkage route to AUD-08. Values written by the agent render through AgentText.

export type NarrativeTab = "risk" | "fraud";

function textOf(cell: WorkpaperCellOut): string {
  const v: unknown = cell.value.v;
  return typeof v === "string" ? v : v === null || v === undefined ? "" : JSON.stringify(v);
}

function Row({
  cell,
  flag,
  onRemind,
  onEscalate,
}: {
  cell: WorkpaperCellOut;
  flag: AttentionFlagOut | undefined;
  onRemind: (flag: AttentionFlagOut) => void;
  onEscalate: (flag: AttentionFlagOut) => void;
}): JSX.Element {
  const label = COPY.rows[cell.row_key ?? ""] ?? "";
  const agent = cell.value_source === "agent";
  return (
    <div
      data-row={cell.row_key ?? cell.cell_key}
      data-state={cell.value_state}
      className="group grid grid-cols-[150px_1fr] gap-[12px] px-[14px] py-[10px] hairline-b"
    >
      <span className="text-[12px] font-medium">{label}</span>
      <div className="flex min-w-0 flex-col gap-[6px] text-[12px] leading-[1.5]">
        {flag !== undefined ? (
          <span
            data-flag={flag.id}
            className="rounded-[3px] bg-amber-tint px-[4px] text-amber-ink"
          >
            {`${COPY.pbcGap} — ${flag.text}`}
          </span>
        ) : agent ? (
          <AgentText text={textOf(cell)} inline className="text-[12px] text-ink" />
        ) : (
          <span>{textOf(cell)}</span>
        )}
        {flag !== undefined && flag.state === "open" && (
          <span className="flex gap-[6px]">
            <Button
              size="sm"
              variant="secondary"
              data-remind={flag.id}
              onClick={() => {
                onRemind(flag);
              }}
            >
              {COPY.remind}
            </Button>
            <Button
              size="sm"
              variant="secondary"
              data-escalate={flag.id}
              onClick={() => {
                onEscalate(flag);
              }}
            >
              {COPY.escalate}
            </Button>
          </span>
        )}
      </div>
    </div>
  );
}

function RiskTab({
  record,
  onRemind,
  onEscalate,
}: {
  record: WorkpaperRecordOut;
  onRemind: (flag: AttentionFlagOut) => void;
  onEscalate: (flag: AttentionFlagOut) => void;
}): JSX.Element {
  const flagOf = (cell: WorkpaperCellOut): AttentionFlagOut | undefined =>
    record.flags.find(
      (f) =>
        f.section_key === cell.section_key && f.row_key === cell.row_key && f.state !== "resolved",
    );
  const loose = record.cells.filter((c) => c.section_key == null);
  return (
    <div data-aud05="risk" className="overflow-hidden rounded-pane bg-card shadow-e1">
      {loose.map((c) => (
        <Row
          key={c.cell_key}
          cell={c}
          flag={flagOf(c)}
          onRemind={onRemind}
          onEscalate={onEscalate}
        />
      ))}
      {record.sections.map((s) => (
        <section key={s.key} data-section={s.key}>
          <h3 className="flex h-[28px] items-center bg-espresso px-[14px] text-micro font-medium uppercase text-on-dark">
            {s.title}
          </h3>
          {record.cells
            .filter((c) => c.section_key === s.key)
            .map((c) => (
              <Row
                key={c.cell_key}
                cell={c}
                flag={flagOf(c)}
                onRemind={onRemind}
                onEscalate={onEscalate}
              />
            ))}
        </section>
      ))}
    </div>
  );
}

function FraudTab({
  engagementId,
  session,
}: {
  engagementId: string;
  session: FraudSessionOut;
}): JSX.Element {
  const queryClient = useQueryClient();
  const path = { path: { engagement_id: engagementId } };
  const approve = useMutation({
    ...fraudMinutesApproveMutation(),
    onSuccess: (next) => {
      queryClient.setQueryData(fraudSessionQueryKey(path), next);
    },
  });
  const may = session.allowed_actions.includes("fraud_minutes.approve");
  return (
    <div data-aud05="fraud" className="flex flex-col gap-[12px]">
      <section className="rounded-pane bg-card p-[12px] shadow-e1">
        <h3 className="mb-[6px] text-section font-medium">{COPY.fraud.session}</h3>
        {session.held_at != null && <p>{dateTime(session.held_at)}</p>}
        {session.led_by != null && (
          <p className="text-ink-2">{COPY.fraud.ledBy(session.led_by.name)}</p>
        )}
        <p data-aud05="attendees" className="mt-[6px]">
          {`${COPY.fraud.attendees}: ${session.attendees.map((a) => a.name).join(", ")}`}
        </p>
        {session.excluded.map((e) => (
          <p key={e.user_id} data-aud05="excluded" className="text-ink-3">
            {(COPY.fraud.excludedReason[e.reason] ?? COPY.fraud.excludedReason.other)?.(e.name)}
          </p>
        ))}
      </section>
      <section className="rounded-pane bg-card p-[12px] shadow-e1">
        <h3 className="mb-[6px] text-section font-medium">{COPY.fraud.discussion}</h3>
        {session.discussion.map((d) => (
          <p key={d.step_key}>{d.summary}</p>
        ))}
      </section>
      <section data-aud05="minutes" className="rounded-pane bg-card p-[12px] shadow-e1">
        <h3 className="mb-[6px] flex items-center gap-[8px] text-section font-medium">
          {COPY.fraud.minutes}
          <Pill
            variant={session.minutes_status === "approved" ? "green-tint" : "amber"}
            size="micro"
          >
            {COPY.fraud.status[session.minutes_status] ?? session.minutes_status}
          </Pill>
        </h3>
        {session.minutes_text != null &&
          (session.minutes_source === "adopted_suggestion" ? (
            <AgentText text={session.minutes_text} />
          ) : (
            <p className="whitespace-pre-line">{session.minutes_text}</p>
          ))}
        {session.approved_by_name != null && (
          <p className="mt-[6px] text-ink-3">{COPY.fraud.approvedBy(session.approved_by_name)}</p>
        )}
        {may && session.minutes_status === "awaiting_approval" && session.minutes_hash != null && (
          <Button
            variant="primary"
            className="mt-[8px]"
            disabled={approve.isPending}
            onClick={() => {
              if (session.minutes_hash == null) return;
              approve.mutate({
                ...path,
                headers: { "Idempotency-Key": crypto.randomUUID() },
                body: { minutes_hash: session.minutes_hash },
              });
            }}
          >
            {COPY.fraud.approve}
          </Button>
        )}
      </section>
    </div>
  );
}

export function NarrativePage({
  auditId,
  workpaperId,
  tab,
  onTab,
  onRegister,
  onEscalate,
  onAdopt,
  onBack,
}: {
  auditId: string;
  workpaperId: string;
  tab: NarrativeTab;
  onTab: (tab: NarrativeTab) => void;
  onRegister: () => void;
  onEscalate: (flag: AttentionFlagOut) => void;
  onAdopt: (workpaperId: string) => void;
  onBack?: () => void;
}): JSX.Element {
  const on = useFlag("assurance.risk_register") === true;
  const cockpit = useAuditCockpit(auditId);
  const engagementId = cockpit.data?.engagement_id;
  const record = useQuery({
    ...workpaperRecordOptions({
      path: { engagement_id: engagementId ?? "", workpaper_id: workpaperId },
      query: { tab: "risk" },
    }),
    enabled: on && engagementId !== undefined,
  });
  const fraud = useQuery({
    ...fraudSessionOptions({ path: { engagement_id: engagementId ?? "" } }),
    enabled: on && engagementId !== undefined && tab === "fraud",
  });
  const remind = useMutation(attentionFlagRemindMutation());
  let state: ViewState = { kind: "ready" };
  if (!on) state = { kind: "flag-off", flag: "assurance.risk_register" };
  else if (cockpit.isError || record.isError) {
    const error = cockpit.error ?? record.error;
    state = isNotFound(error)
      ? { kind: "restricted", reason: "walled" }
      : { kind: "error", retry: () => void record.refetch() };
  } else if (record.data === undefined) state = { kind: "loading" };
  const data = record.data;
  const citations = new Set((data?.cells ?? []).flatMap((c) => c.citation_ids)).size;
  const reviewed = (data?.sign_offs ?? []).find(
    (s) => s.level !== "L1" && s.initials != null && !s.stale,
  );
  const drafted = (data?.cells ?? []).some((c) => c.value_state === "suggested");
  const labels: Record<NarrativeTab, string> = { risk: COPY.tabs[0], fraud: COPY.tabs[1] };
  return (
    <div data-screen="AUD-05" data-tab={tab} className="flex min-h-0 flex-1 flex-col">
      {cockpit.data !== undefined && (
        <AuditBar cockpit={cockpit.data} {...(onBack === undefined ? {} : { onBack })} />
      )}
      <ViewStateBody state={state} empty={{ title: COPY.title }}>
        {data !== undefined && engagementId !== undefined && (
          <div className="flex min-h-0 flex-1 flex-col">
            <header className="flex h-[46px] items-center justify-center gap-[8px] px-[12px]">
              <h2 className="text-[14.5px] font-medium">{COPY.title}</h2>
              <Pill variant="tag" size="micro">
                {COPY.version(data.version_no)}
              </Pill>
              {drafted && (
                <Pill variant="neutral" size="micro">
                  {COPY.agentDraft}
                </Pill>
              )}
              {reviewed?.initials != null && (
                <Pill data-reviewed="" variant="green-tint" size="micro">
                  {COPY.reviewed(reviewed.initials)}
                </Pill>
              )}
            </header>
            <div className="flex h-[42px] items-center gap-[8px] px-[12px]">
              <Segmented
                size="small"
                label={COPY.title}
                options={COPY.tabs}
                active={labels[tab]}
                onChange={(label) => {
                  if (label === COPY.tabs[1]) onTab("fraud");
                  else if (label === COPY.tabs[0]) onTab("risk");
                  else onRegister();
                }}
              />
              <span className="flex-1" />
              <PaneAction icon="file-spreadsheet" label={COPY.openExcel} />
            </div>
            <div className="flex min-h-0 flex-1 flex-col gap-[12px] overflow-auto p-[12px]">
              {(remind.isSuccess || remind.isError) && tab === "risk" && (
                <p data-aud05="remind-status" role="status" className="text-[12px] text-ink-2">
                  {remind.isSuccess
                    ? COPY.reminded
                    : errorCode(remind.error) === "nothing_to_remind"
                      ? COPY.remindNothing
                      : COPY.remindFailed}
                </p>
              )}
              {tab === "risk" ? (
                <RiskTab
                  record={data}
                  onRemind={(flag) => {
                    remind.mutate({
                      path: {
                        engagement_id: engagementId,
                        workpaper_id: data.id,
                        flag_id: flag.id,
                      },
                      headers: { "Idempotency-Key": crypto.randomUUID() },
                    });
                  }}
                  onEscalate={onEscalate}
                />
              ) : fraud.data !== undefined ? (
                <FraudTab engagementId={engagementId} session={fraud.data} />
              ) : null}
            </div>
            <footer className="flex h-[40px] items-center gap-[8px] px-[12px] hairline-t">
              <PaneAction label={COPY.citations(citations)} />
              <PaneAction label={COPY.procedures} />
              <span className="flex-1" />
              {drafted && (
                <PaneAction
                  icon="check"
                  label={COPY.adopt}
                  onClick={() => {
                    onAdopt(data.id);
                  }}
                />
              )}
              <PaneAction icon="arrow-up-right" label={COPY.openRegister} onClick={onRegister} />
            </footer>
          </div>
        )}
      </ViewStateBody>
    </div>
  );
}

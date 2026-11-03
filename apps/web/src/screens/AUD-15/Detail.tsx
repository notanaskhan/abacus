import type { FindingDetailOut, LateRemittanceOut } from "@abacus/api-client";
import {
  findingNotApplicableMutation,
  findingRequestDecisionMutation,
  findingResolveMutation,
} from "@abacus/api-client/query";
import { AgentText, Button, Icon, Pill, StatusDisc, cn, date, time, toast } from "@abacus/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { JSX, ReactNode } from "react";
import { useNow } from "../../app-core/clock";
import { useOpenOverlay } from "../../app-core/open";
import { useDecisionCard } from "../../domain/review";
import { ov } from "../../routes/to";
import { COPY } from "./copy";

// AUD-15's detail (A-06-T18): the finding's title band, its KV rows, Why This Was Surfaced (the
// olive check disc, never an agent glyph), the evaluation or, for a projected misstatement, the
// projection, the linked entities and the footer. The severity picker is the engagement
// partner's alone: for everyone else it is read-only with "Reserved to Engagement Partner"; the
// partner's Conclude severity… opens SHL-11 on the finding's card. Requesting the decision, Resolve
// and Mark Not Applicable are the person's (the server's `allowed_actions`); Convert opens the
// convert sheet (`?ov=convert:<id>`). The agent concludes nothing (ADR-005).

function Kv({ k, children }: { k: string; children: ReactNode }): JSX.Element {
  return (
    <div className="flex h-[35px] items-center gap-[8px] px-[14px] hairline-b">
      <span className="flex-1 text-body text-ink-2">{k}</span>
      <span className="flex items-center gap-[6px] text-body font-medium">{children}</span>
    </div>
  );
}

function Band({ title, glyph }: { title: string; glyph?: ReactNode }): JSX.Element {
  return (
    <h3 className="flex h-[38px] items-center gap-[8px] bg-band-hd px-[14px] text-[13.5px] font-medium hairline-b">
      {glyph}
      {title}
    </h3>
  );
}

function useCard(detail: FindingDetailOut) {
  const cardId = detail.decision_card_id;
  const card = useDecisionCard(cardId ?? "");
  return cardId === null ? undefined : card.data;
}

export function FindingDetail({
  detail,
  remittances,
  lit,
  onLight,
}: {
  detail: FindingDetailOut;
  remittances: readonly LateRemittanceOut[];
  lit: string | null;
  onLight: (id: string) => void;
}): JSX.Element {
  const now = useNow();
  const openOverlay = useOpenOverlay();
  const f = detail.finding;
  const card = useCard(detail);
  const decideCard =
    card?.card.allowed_actions.includes("decision.decide") === true ? card : undefined;
  const reserved = decideCard !== undefined;
  const severity = f.severity_concluded ?? f.severity_proposed;
  const strong = severity === "significant_deficiency" || severity === "material_weakness";
  const proposed = f.deficiency_status === "proposed";
  const decided = card?.decision ?? null;
  const projection = COPY.projectionKeys.filter((k) => detail.evaluation[k] !== undefined);
  const evaluation = Object.entries(detail.evaluation).filter(
    ([k]) => !(COPY.projectionKeys as readonly string[]).includes(k),
  );
  return (
    <article data-aud15="detail" data-finding={f.ref} className="flex flex-col">
      <h2 className="bg-shell px-[14px] py-[12px] text-[15px] leading-[1.3] font-medium tracking-[-0.012em] hairline-b">
        {f.title}
      </h2>
      <Kv k={COPY.kv.type}>
        {COPY.kind[f.kind]}
        {projection.length > 0 && (
          <Pill variant="tag" size="micro">
            {COPY.projection}
          </Pill>
        )}
      </Kv>
      {f.coso_component !== null && <Kv k={COPY.kv.coso}>{COPY.coso[f.coso_component]}</Kv>}
      {severity !== null && (
        <Kv k={COPY.kv.severity}>
          <Pill
            variant={strong ? "red" : "red-tint"}
            size="state"
            className={cn(severity === "material_weakness" && "font-medium")}
          >
            {COPY.severity[severity]}
          </Pill>
          {proposed && (
            <Pill variant="amber" size="state">
              {COPY.status.proposed}
            </Pill>
          )}
          <button
            type="button"
            data-aud15="severity-picker"
            aria-label={reserved ? COPY.footer.concludeSeverity : COPY.reserved}
            title={reserved ? undefined : COPY.reserved}
            disabled={!reserved}
            {...(decideCard !== undefined
              ? {
                  onClick: () => {
                    openOverlay(ov.SHL11(decideCard.card.id));
                  },
                }
              : {})}
            className="text-ink-3 disabled:cursor-default"
          >
            <Icon name="chevron-down" size={12} />
          </button>
        </Kv>
      )}
      {f.deficiency_status !== null && (
        <Kv k={COPY.kv.status}>
          <Pill
            variant={
              f.deficiency_status === "communicated"
                ? "green-tint"
                : f.deficiency_status === "concluded"
                  ? "neutral"
                  : "amber"
            }
            size="state"
          >
            {COPY.status[f.deficiency_status]}
          </Pill>
        </Kv>
      )}
      {decided !== null && (
        <p
          data-aud15="concluded"
          className="px-[14px] py-[8px] text-dense text-green-ink hairline-b"
        >
          {COPY.concludedBy(
            decided.decided_by_name,
            `${date(decided.decided_at, { now })}, ${time(decided.decided_at)}`,
          )}
        </p>
      )}
      <Kv k={COPY.kv.createdBy}>{f.created_by_name}</Kv>
      {detail.why_surfaced !== null && (
        <>
          <Band title={COPY.why} glyph={<StatusDisc state="done" />} />
          <AgentText
            text={detail.why_surfaced}
            className="block px-[14px] py-[12px] text-[12.5px] leading-[1.55] text-ink-2"
          />
        </>
      )}
      {evaluation.length > 0 && (
        <section data-aud15="evaluation">
          <Band title={COPY.evaluation} />
          {evaluation.map(([k, v]) => (
            <div
              key={k}
              className="flex min-h-[30px] items-center gap-[12px] px-[14px] hairline-b"
            >
              <span className="w-[160px] flex-none text-[12.5px] text-ink-2">
                {COPY.evaluationKeys[k] ?? k}
              </span>
              <span className="flex-1 text-right text-[12.5px]">{v}</span>
            </div>
          ))}
        </section>
      )}
      {projection.length > 0 && (
        <section data-aud15="projection">
          <Band title={COPY.projection} />
          {projection.map((k) => (
            <div
              key={k}
              className="flex min-h-[30px] items-center gap-[12px] px-[14px] hairline-b"
            >
              <span className="w-[160px] flex-none text-[12.5px] text-ink-2">
                {COPY.evaluationKeys[k] ?? k}
              </span>
              <span className="flex-1 text-right text-[12.5px] tabular-nums">
                {detail.evaluation[k]}
              </span>
            </div>
          ))}
        </section>
      )}
      {remittances.length > 0 && (
        <section data-aud15="linked">
          <Band
            title={COPY.linked}
            glyph={<Icon name="flag" size={12} className={strong ? "text-red" : "text-amber"} />}
          />
          <div className="flex flex-wrap gap-[6px] px-[14px] py-[10px]">
            {remittances.map((r) => (
              <button
                key={r.id}
                type="button"
                data-aud15="file-chip"
                {...(lit === r.id ? { "data-lit": "" } : {})}
                onClick={() => {
                  onLight(r.id);
                }}
                className={cn(
                  "rounded-full px-[10px] py-[3px] text-dense shadow-e1",
                  lit === r.id ? "bg-match-bg ring-1 ring-match-line" : "bg-card",
                )}
              >
                {COPY.evidence.chip(date(r.payroll_date, { now }))}
              </button>
            ))}
          </div>
        </section>
      )}
    </article>
  );
}

export function FindingFooter({ detail }: { detail: FindingDetailOut }): JSX.Element | null {
  const openOverlay = useOpenOverlay();
  const queryClient = useQueryClient();
  const f = detail.finding;
  const card = useCard(detail);
  const allowed = detail.allowed_actions;
  const refresh = (): void => {
    void queryClient.invalidateQueries({ queryKey: [{ _id: "auditFindings" }] });
    void queryClient.invalidateQueries({ queryKey: [{ _id: "auditFinding" }] });
  };
  const failed = (): void => {
    toast.show({ kind: "error", text: COPY.failed });
  };
  const request = useMutation({
    ...findingRequestDecisionMutation(),
    onSuccess: () => {
      toast.show({ kind: "success", text: COPY.sent("Margaret Okonkwo") });
      refresh();
    },
    onError: failed,
  });
  const resolve = useMutation({
    ...findingResolveMutation(),
    onSuccess: refresh,
    onError: failed,
  });
  const notApplicable = useMutation({
    ...findingNotApplicableMutation(),
    onSuccess: refresh,
    onError: failed,
  });
  const path = { finding_id: f.id };
  const key = (): { "Idempotency-Key": string } => ({ "Idempotency-Key": crypto.randomUUID() });
  const buttons: ReactNode[] = [];
  const decideCard =
    card?.card.allowed_actions.includes("decision.decide") === true ? card : undefined;
  if (decideCard !== undefined) {
    buttons.push(
      <Button
        key="conclude"
        variant="primary"
        icon="scale"
        onClick={() => {
          openOverlay(ov.SHL11(decideCard.card.id));
        }}
      >
        {COPY.footer.concludeSeverity}
      </Button>,
    );
  } else if (allowed.includes("finding.request_decision")) {
    buttons.push(
      <Button
        key="request"
        variant="primary"
        icon="scale"
        disabled={request.isPending}
        onClick={() => {
          request.mutate({ path, headers: key() });
        }}
      >
        {COPY.footer.requestDecision}
      </Button>,
    );
  } else if (f.deficiency_status === "concluded") {
    buttons.push(
      <Button key="letter" variant="primary" disabled>
        {COPY.footer.addToLetter}
      </Button>,
    );
  }
  if (allowed.includes("finding.resolve")) {
    buttons.push(
      <Button
        key="resolve"
        variant="primary"
        icon="check"
        disabled={resolve.isPending}
        onClick={() => {
          resolve.mutate({ path, body: { reason_code: "resolved" }, headers: key() });
        }}
      >
        {COPY.footer.resolve}
      </Button>,
    );
  }
  if (allowed.includes("finding.convert")) {
    const exception = f.deficiency_status === "exception_for_resolution";
    buttons.push(
      <Button
        key="convert"
        variant="tonal"
        onClick={() => {
          openOverlay({ key: "convert", args: [f.id] });
        }}
      >
        {exception ? COPY.footer.convertDeficiency : COPY.footer.convertMisstatement}
      </Button>,
    );
  }
  if (allowed.includes("finding.mark_not_applicable")) {
    buttons.push(
      <Button
        key="na"
        variant="secondary"
        disabled={notApplicable.isPending}
        onClick={() => {
          notApplicable.mutate({ path, body: { reason_code: "not_applicable" }, headers: key() });
        }}
      >
        {COPY.footer.notApplicable}
      </Button>,
    );
  }
  if (buttons.length === 0) return null;
  return (
    <div data-aud15="footer" className="flex flex-col gap-[8px] p-[10px] [&>button]:h-[36px]">
      {buttons}
    </div>
  );
}

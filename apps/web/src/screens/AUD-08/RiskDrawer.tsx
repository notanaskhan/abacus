import type { RegisterRiskOut } from "@abacus/api-client";
import {
  decisionCardNotifyMutation,
  riskDrawerOptions,
  suggestionAdoptMutation,
  suggestionDismissMutation,
} from "@abacus/api-client/query";
import { AgentText, Button, Drawer, Pill, time, toast } from "@abacus/ui";
import { useMutation, useQuery } from "@tanstack/react-query";
import type { JSX } from "react";
import { DraftedFooter, DraftedMarker } from "./AgentStates";
import { COPY } from "./copy";

// AUD-08 b and b2 (A-04-T20): the O2 rationale drawer (480) over `GET …/risks/{rid}`: the SAS 145
// factors, the rationale with its citation count, the relevant assertions and the versions. The
// footer is the person's: whoever routed it reads "Routed to … · time" with Remind…; the reserved
// engagement partner (the server's `decision.decide` on the row) gets "Approve as significant
// risk", which opens SHL-11 on the `significant_risk` card with the subject preselected.

export function RiskDrawer({
  engagementId,
  risk,
  onClose,
  onDecide,
  onEdit,
}: {
  engagementId: string;
  risk: RegisterRiskOut;
  onClose: () => void;
  onDecide: (cardId: string, subject: string) => void;
  /** Edit the drafted rationale in the host's editor; the model's text is never sent back as a
   * person's edit (ADR-065). */
  onEdit?: () => void;
}): JSX.Element {
  const drawer = useQuery(
    riskDrawerOptions({ path: { engagement_id: engagementId, risk_id: risk.id } }),
  );
  const data = drawer.data;
  // A-04-T26 (f): a drafted rationale waits for a person (C-31); nothing adopts by itself.
  const suggestionId = data?.rationale_suggestion_id ?? null;
  const drafted = suggestionId !== null;
  const refresh = (): void => {
    void drawer.refetch();
  };
  const adopt = useMutation({ ...suggestionAdoptMutation(), onSuccess: refresh });
  const dismiss = useMutation({ ...suggestionDismissMutation(), onSuccess: refresh });
  // The drawer's read says who the awaiting card waits for and what this person may do about it;
  // the register's rows do not carry either (DEC-2420).
  const cardId = data?.pending_card_id ?? null;
  const actions = data?.risk.allowed_actions ?? risk.allowed_actions;
  const decides = actions.includes("decision.decide");
  const routedTo = data?.routed_to_name ?? null;
  const notify = useMutation({
    ...decisionCardNotifyMutation(),
    onSuccess: () => {
      if (routedTo !== null) toast.show({ kind: "success", text: COPY.drawer.reminded(routedTo) });
    },
  });
  const footer =
    decides && cardId !== null ? (
      <div data-aud08="partner-footer" className="flex items-center gap-[8px]">
        <Button
          variant="primary"
          onClick={() => {
            onDecide(cardId, risk.code);
          }}
        >
          {COPY.drawer.approve}
        </Button>
        <Button
          variant="secondary"
          onClick={() => {
            onDecide(cardId, risk.code);
          }}
        >
          {COPY.drawer.notSignificant}
        </Button>
      </div>
    ) : routedTo !== null && data?.routed_at != null ? (
      <div data-aud08="routed-footer" className="flex items-center gap-[8px]">
        <span className="flex-1 text-[11.5px] text-ink-3">
          {COPY.drawer.routed(routedTo, time(data.routed_at))}
        </span>
        {cardId !== null && actions.includes("decision.notify") && (
          <Button
            variant="secondary"
            icon="bell"
            disabled={notify.isPending}
            onClick={() => {
              notify.mutate({ path: { card_id: cardId } });
            }}
          >
            {COPY.drawer.remind(routedTo.split(" ")[0] ?? routedTo)}
          </Button>
        )}
      </div>
    ) : undefined;
  return (
    <Drawer
      open
      width={480}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={`${risk.code} · ${risk.area_label}`}
      {...(footer === undefined ? {} : { footer })}
    >
      <div data-aud08="drawer" data-risk={risk.code} className="flex flex-col gap-[12px] p-[12px]">
        <section className="rounded-pane bg-card p-[12px] shadow-e1">
          <h3 className="mb-[8px] text-section font-medium">{COPY.drawer.factors}</h3>
          {risk.inherent_factors.map((f) => (
            <div key={f.factor} data-factor={f.factor} className="flex h-[24px] items-center">
              <span className="flex-1 text-ink-2">{COPY.drawer.factor[f.factor] ?? f.factor}</span>
              <span>{COPY.rating[f.rating] ?? f.rating}</span>
            </div>
          ))}
        </section>
        <section data-aud08="rationale" className="rounded-pane bg-card p-[12px] shadow-e1">
          <h3 className="mb-[8px] flex items-center text-section font-medium">
            {COPY.drawer.rationaleCard}
            {drafted && <DraftedMarker citations={data?.citation_ids.length ?? 0} />}
          </h3>
          <AgentText
            text={data?.rationale ?? ""}
            className={
              drafted
                ? "text-[12.5px] leading-[1.55] text-ink-2"
                : "text-[12.5px] leading-[1.55] text-ink"
            }
          />
          {(data?.citation_ids.length ?? 0) > 0 && (
            <p className="mt-[8px] text-micro text-ink-3">
              {COPY.drawer.citations(data?.citation_ids.length ?? 0)}
            </p>
          )}
          {suggestionId !== null && (
            <DraftedFooter
              onAdopt={() => {
                adopt.mutate({ path: { suggestion_id: suggestionId }, body: { seen_version: 1 } });
              }}
              onEdit={() => {
                onEdit?.();
              }}
              onDiscard={() => {
                dismiss.mutate({
                  path: { suggestion_id: suggestionId },
                  body: { seen_version: 1 },
                });
              }}
            />
          )}
        </section>
        <section className="rounded-pane bg-card p-[12px] shadow-e1">
          <h3 className="mb-[8px] text-section font-medium">{COPY.drawer.assertions}</h3>
          <div className="flex flex-wrap gap-[6px]">
            {risk.assertions.map((a) => (
              <Pill key={a} variant="tag" size="micro">
                {COPY.assertion[a] ?? a}
              </Pill>
            ))}
          </div>
        </section>
        <section data-aud08="versions" className="rounded-pane bg-card p-[12px] shadow-e1">
          <h3 className="mb-[8px] text-section font-medium">{COPY.drawer.versions}</h3>
          {(data?.versions ?? []).map((v) => (
            <div key={v.version_no} className="flex h-[24px] items-center gap-[8px]">
              <span>{`v${String(v.version_no)}`}</span>
              <span className="text-ink-3">{time(v.at)}</span>
              <span className="text-ink-3">{v.by_name}</span>
            </div>
          ))}
        </section>
      </div>
    </Drawer>
  );
}

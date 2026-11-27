// TAX-15 · Planning opportunities (T-08-T32; TASK-9033; DEC-6038) on T9's close-review preset at
// `/tax-returns/planning`, behind `tax.planning`: the portfolio strip, a queue banded by status
// with rings, the detail (KV rows, "Why This Was Surfaced" with the olive check disc, the footer
// stack) and the evidence pane (sources, the 2-Year Comparison). Every figure, word and action is
// the server's; the rationale is agent text (AgentText). A raise is a person's act: Raise with
// client… drafts the message in an O3 sheet (until INB-04) and sends only on Daniel's click.
// Create advisory project… prefills ENG-03; Dismiss… needs a reason. A consent-blocked row shows
// the amber banner and only Open consent envelope (SIG-02), never an outreach control.
import type { TaxPracticeOpportunityOut, TaxPracticeRaiseSheetOut } from "@abacus/api-client";
import {
  planningCreateProjectMutation,
  planningDismissMutation,
  planningOpportunitiesOptions,
  planningOpportunitiesQueryKey,
  planningPrepareRaiseMutation,
  planningRaiseMutation,
  planningSummaryOptions,
} from "@abacus/api-client/query";
import {
  AgentText,
  Button,
  Dialog,
  Icon,
  Pill,
  SheetModal,
  Skeleton,
  amount,
  date,
  toast,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { type JSX, useState } from "react";
import { useNow } from "../../app-core/clock";
import { useOpenHref, useOpenOverlay } from "../../app-core/open";
import { useSession } from "../../app-core/session";
import { hrefOf, ov, to } from "../../routes/to";
import { COPY as C } from "./copy";

type Opp = TaxPracticeOpportunityOut;
type Reason = "not_suitable" | "already_in_place" | "client_declined" | "other";
const BANDS = ["open", "raised", "accepted", "declined", "not_screened", "dismissed"] as const;

export interface TAX15Props {
  initialSelected?: string;
  /** The per-return view (f): the client chip active. */
  clientId?: string;
  initialDismissDialog?: boolean;
}

function idempotency(): { "Idempotency-Key": string } {
  return { "Idempotency-Key": `tax15-${crypto.randomUUID()}` };
}

function Ring({ status }: { status: Opp["status"] }): JSX.Element {
  const icon =
    status === "raised"
      ? "circle-dot"
      : status === "accepted"
        ? "circle-check"
        : status === "declined" || status === "dismissed"
          ? "circle-x"
          : status === "not_screened"
            ? "triangle-alert"
            : "circle";
  const tone =
    status === "accepted"
      ? "text-green"
      : status === "not_screened"
        ? "text-amber"
        : status === "declined" || status === "dismissed"
          ? "text-ink-4"
          : "text-ink-3";
  return (
    <Icon name={icon} size={15} className={`flex-none ${tone}`} label={C.band[status] ?? status} />
  );
}

export function TAX15({
  initialSelected,
  clientId,
  initialDismissDialog = false,
}: TAX15Props): JSX.Element {
  const now = useNow();
  const navigate = useNavigate();
  const openOverlay = useOpenOverlay();
  const openHref = useOpenHref();
  const queries = useQueryClient();
  const viewer = useSession().user?.displayName ?? "";
  const [client, setClient] = useState<string | undefined>(clientId);
  const [dismissed, setDismissed] = useState(false);
  const query = {
    ...(client === undefined ? {} : { client_id: client }),
    ...(dismissed ? { include_dismissed: true } : {}),
  };
  const list = useQuery(planningOpportunitiesOptions({ query }));
  // The portfolio year: the tax year the returns were filed for (TY2025 in the 2026 season).
  const year = now.getFullYear() - 1;
  const summary = useQuery(planningSummaryOptions({ query: { tax_year: year } }));
  const [selectedId, setSelected] = useState<string | undefined>(initialSelected);
  const [sheet, setSheet] = useState<TaxPracticeRaiseSheetOut | null>(null);
  const [dismissing, setDismissing] = useState(initialDismissDialog);
  const [reason, setReason] = useState<Reason | null>(null);
  const refresh = () =>
    queries.invalidateQueries({ queryKey: planningOpportunitiesQueryKey({ query }) });
  const prepare = useMutation({
    ...planningPrepareRaiseMutation(),
    onSuccess: setSheet,
    onError: () => toast.show({ kind: "error", text: C.failed }),
  });
  const raise = useMutation({
    ...planningRaiseMutation(),
    onSuccess: async () => {
      setSheet(null);
      toast.show({ kind: "info", text: C.raised });
      await refresh();
    },
    onError: () => toast.show({ kind: "error", text: C.failed }),
  });
  const project = useMutation({
    ...planningCreateProjectMutation(),
    onSuccess: (prefill) => {
      // ENG-03 opens prefilled from the opportunity (then PRJ-01 Scoping).
      openHref(
        hrefOf(to.ENG03(), {
          name: prefill.engagement_name,
          client: prefill.client_id,
          source: prefill.source_ref,
        }),
      );
    },
    onError: () => toast.show({ kind: "error", text: C.failed }),
  });
  const dismiss = useMutation({
    ...planningDismissMutation(),
    onSuccess: async () => {
      setDismissing(false);
      setReason(null);
      await refresh();
    },
    onError: () => toast.show({ kind: "error", text: C.failed }),
  });
  const items = list.data?.items ?? [];
  const selected = items.find((o) => o.opportunity_id === selectedId) ?? items[0];
  const s = summary.data;

  if (list.isError) {
    return (
      <div
        data-screen="TAX-15"
        role="alert"
        className="flex flex-col items-start gap-[8px] p-[24px]"
      >
        <p className="text-[13px]">{C.loadFailed}</p>
        <Button variant="secondary" size="sm" onClick={() => void list.refetch()}>
          {C.retry}
        </Button>
      </div>
    );
  }
  if (list.data === undefined) {
    return (
      <div data-screen="TAX-15" aria-busy="true" className="p-[12px]">
        <Skeleton className="h-[600px] w-full" />
      </div>
    );
  }
  const blocked = selected?.status === "not_screened";
  const why = selected?.rationale ?? null;
  const may = (a: string) => (selected?.allowed_actions ?? []).includes(a);
  return (
    <div data-screen="TAX-15" className="flex min-h-0 flex-1 flex-col">
      <div className="relative flex h-[42px] flex-none items-center px-[12px]">
        <button
          type="button"
          className="z-10 flex h-[29px] items-center gap-[4px] rounded-full bg-card px-[10px] text-[13px] shadow-e1"
          onClick={() => void navigate(to.TAX01())}
        >
          <Icon name="chevron-left" size={14} />
          {C.back}
        </button>
        <h1 className="absolute inset-x-0 text-center text-[15px]">
          <span className="font-medium">{C.title}</span>{" "}
          <span className="text-ink-2">{C.scope(s?.tax_year ?? 2025, viewer)}</span>
        </h1>
        {client === undefined ? null : (
          <button
            type="button"
            data-tax15="client-chip"
            className="z-10 ml-auto flex h-[29px] items-center gap-[6px] rounded-full bg-amber-tint px-[10px] text-[13px] text-amber-ink"
            onClick={() => {
              setClient(undefined);
            }}
          >
            {C.clientChip(items[0]?.client_name ?? "")}
            <Icon name="x" size={12} />
          </button>
        )}
      </div>
      <div className="flex h-[52px] flex-none items-center gap-[8px] px-[12px]" data-tax15="strip">
        {s === undefined ? null : (
          <>
            <Card label={C.strip.contact} value={String(s.clients_to_contact)} />
            <Card label={C.strip.savings} value={`$${amount(s.est_savings, "whole").text}`} />
            <Card label={C.strip.talking}>
              <Pill variant={s.talking_points === "drafted" ? "green" : "neutral"}>
                {C.talking[s.talking_points]}
              </Pill>
            </Card>
            <Card label={C.strip.blocked}>
              <Pill variant="amber">{String(s.consent_blocked)}</Pill>
            </Card>
          </>
        )}
      </div>
      <div className="flex min-h-0 flex-1 gap-[10px] px-[12px] pb-[12px]">
        <div className="flex min-h-0 w-[790px] flex-none overflow-hidden rounded-[12px] bg-card shadow-e1">
          <section aria-label={C.queue} className="flex w-[310px] flex-none flex-col hairline-r">
            <header className="relative flex h-[46px] flex-none items-center justify-center text-[14px] font-medium">
              {C.queue}
              <button
                type="button"
                aria-pressed={dismissed}
                className="absolute right-[10px] text-[13px] font-normal text-ink-3"
                onClick={() => {
                  setDismissed(!dismissed);
                }}
              >
                {C.showDismissed}
              </button>
            </header>
            <div className="min-h-0 flex-1 overflow-auto">
              {BANDS.map((band) => {
                const rows = items.filter((o) => o.status === band);
                if (rows.length === 0) return null;
                return (
                  <div key={band} data-band={band}>
                    <p className="flex h-[31px] items-center gap-[6px] bg-band-hd px-[12px] text-[14px]">
                      {C.band[band]} <span className="text-[12px] text-ink-3">{rows.length}</span>
                    </p>
                    {rows.map((o) => (
                      <button
                        key={o.opportunity_id}
                        type="button"
                        data-opportunity={o.opportunity_id}
                        aria-current={
                          o.opportunity_id === selected?.opportunity_id ? "true" : undefined
                        }
                        className={`flex w-full gap-[8px] px-[12px] py-[8px] text-left hairline-b ${
                          o.opportunity_id === selected?.opportunity_id
                            ? "bg-sel-bg font-medium"
                            : ""
                        } ${band === "dismissed" ? "text-ink-3" : ""}`}
                        onClick={() => {
                          setSelected(o.opportunity_id);
                        }}
                      >
                        <Ring status={o.status} />
                        <span className="flex min-w-0 flex-col">
                          <span className="line-clamp-2 text-[13px] leading-[1.32]">
                            {o.title}
                          </span>
                          <span className="text-[11.5px] font-normal text-ink-3">
                            {o.est_savings
                              ? C.sub(o.client_name, amount(o.est_savings, "whole").text)
                              : o.client_name}
                          </span>
                        </span>
                      </button>
                    ))}
                  </div>
                );
              })}
            </div>
            <p className="flex-none px-[12px] py-[6px] text-[11.5px] text-ink-3">
              {C.showing(items.length, list.data.total, s?.clients ?? 0)}
            </p>
          </section>
          {selected === undefined ? null : (
            <section
              aria-label={C.detail}
              className="flex min-w-0 flex-1 flex-col"
              data-tax15="detail"
            >
              <h2 className="bg-shell px-[14px] py-[12px] text-[15px] font-medium">
                {selected.title}
              </h2>
              <div className="min-h-0 flex-1 overflow-auto">
                {blocked ? (
                  <p
                    role="status"
                    data-tax15="consent-banner"
                    className="m-[12px] rounded-nested bg-amber-tint px-[12px] py-[9px] text-[12.5px] text-amber-ink"
                  >
                    {C.consentBlocked}
                  </p>
                ) : null}
                <dl>
                  <Kv k={C.keys.client}>
                    <a
                      href={hrefOf(to.CLI02({ clientId: selected.client_id }))}
                    >{`${selected.client_name} ›`}</a>
                  </Kv>
                  <Kv k={C.keys.profile}>
                    {/* The client's tax profile and consents (CLI-05). */}
                    <a href={hrefOf(to.CLI05({ clientId: selected.client_id, sub: "profile" }))}>
                      {C.openProfile}
                    </a>
                  </Kv>
                  {selected.work_item_id ? (
                    <Kv k={C.keys.return}>
                      <a href={hrefOf(to.TAX02({ returnId: selected.work_item_id }))}>
                        {C.returnValue(selected.tax_year ?? 2025)}
                      </a>
                    </Kv>
                  ) : null}
                  <Kv k={C.keys.status}>
                    <span className="inline-flex items-center gap-[6px]">
                      <Ring status={selected.status} />
                      {C.band[selected.status]}
                      {selected.raised_at
                        ? ` · ${C.raisedOn(date(selected.raised_at, { now }))}`
                        : ""}
                    </span>
                  </Kv>
                  <Kv k={C.keys.savings}>
                    {selected.est_savings ? amount(selected.est_savings, "whole").text : "—"}
                  </Kv>
                  <Kv k={C.keys.owner}>{viewer}</Kv>
                  {selected.consent_basis ? (
                    <Kv k={C.keys.consent}>
                      <Pill variant="green">
                        {C.consentBasis[selected.consent_basis] ?? selected.consent_basis}
                      </Pill>
                    </Kv>
                  ) : null}
                </dl>
                {why !== null ? (
                  <section aria-label={C.why} className="px-[14px] py-[12px]" data-tax15="why">
                    <h3 className="flex items-center gap-[8px] text-[13.5px] font-medium">
                      <Icon name="circle-check" size={15} className="text-green" />
                      {C.why}
                    </h3>
                    <AgentText
                      text={why}
                      className="mt-[6px] text-[12.5px] leading-[1.55] text-ink-2"
                    />
                  </section>
                ) : null}
              </div>
              <div className="flex flex-col gap-[8px] p-[10px] hairline-t">
                {blocked ? (
                  selected.consent_envelope_id ? (
                    <Button
                      variant="primary"
                      onClick={() => {
                        if (selected.consent_envelope_id)
                          openOverlay(ov.SIG02(selected.consent_envelope_id));
                      }}
                    >
                      {C.openEnvelope}
                    </Button>
                  ) : null
                ) : (
                  <>
                    <Button
                      variant="primary"
                      disabled={!may("planning.raise") || prepare.isPending}
                      onClick={() => {
                        prepare.mutate({
                          path: { opportunity_id: selected.opportunity_id },
                          headers: idempotency(),
                        });
                      }}
                    >
                      {C.raise}
                    </Button>
                    <Button
                      variant="secondary"
                      disabled={!may("planning.create_project") || project.isPending}
                      onClick={() => {
                        project.mutate({
                          path: { opportunity_id: selected.opportunity_id },
                          headers: idempotency(),
                        });
                      }}
                    >
                      {C.createProject}
                    </Button>
                    <Button
                      variant="secondary"
                      disabled={!may("planning.dismiss")}
                      onClick={() => {
                        setDismissing(true);
                      }}
                    >
                      {C.dismiss}
                    </Button>
                  </>
                )}
              </div>
            </section>
          )}
        </div>
        <section
          aria-label={C.evidence}
          className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-[12px] bg-card shadow-e1"
        >
          <header className="flex h-[46px] flex-none items-center justify-center text-[14px] font-medium">
            {C.evidence}
          </header>
          <div className="flex min-h-0 flex-1 flex-col gap-[12px] overflow-auto bg-shell p-[12px]">
            {selected?.work_item_id ? (
              <div className="rounded-[10px] bg-card p-[12px] shadow-e1">
                <a
                  href={hrefOf(to.TXP01({ returnId: selected.work_item_id, section: "summary" }))}
                  className="mb-[6px] block text-[12.5px] font-medium"
                >
                  {C.openMemo}
                </a>
                <p className="text-[13px] font-medium">{C.twoYear}</p>
                <a
                  href={hrefOf(to.TAX10({ returnId: selected.work_item_id, section: "two-year" }))}
                  className="text-[12.5px] font-medium"
                >
                  {C.openTwoYear}
                </a>
              </div>
            ) : null}
            {(selected?.citations ?? []).length > 0 ? (
              <div className="rounded-[10px] bg-card p-[12px] shadow-e1" data-tax15="sources">
                <p className="pb-[6px] text-[13px] font-medium">{C.source}</p>
                <ul className="flex flex-col gap-[6px]">
                  {(selected?.citations ?? []).map((c) => (
                    <li key={c.citation_id} className="flex items-center gap-[6px] text-[12.5px]">
                      <Icon name="file-text" size={12} className="text-ink-3" />
                      {c.label}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        </section>
      </div>
      <SheetModal
        open={sheet !== null}
        onOpenChange={(open) => {
          if (!open) setSheet(null);
        }}
        title={C.raiseTitle}
        action={
          <Button
            variant="primary"
            size="sm"
            disabled={raise.isPending || sheet === null}
            onClick={() => {
              if (sheet === null || selected === undefined) return;
              raise.mutate({
                path: { opportunity_id: selected.opportunity_id },
                body: {
                  subject: sheet.subject,
                  body: sheet.body,
                  recipient_contact_ids: sheet.recipient_contact_ids ?? [],
                },
                headers: idempotency(),
              });
            }}
          >
            {C.send}
          </Button>
        }
      >
        {sheet === null ? null : (
          <div className="flex flex-col gap-[10px] p-[14px] text-[13px]" data-tax15="raise-sheet">
            <p>
              <span className="text-ink-3">{C.recipientsLabel}</span> {sheet.recipients.join(", ")}
            </p>
            <p className="font-medium">{sheet.subject}</p>
            <AgentText
              text={sheet.body}
              className="whitespace-pre-line text-[12.5px] leading-[1.55]"
            />
            {sheet.draft_from_agent ? (
              <p className="text-[11.5px] text-ink-3">{C.draftNote}</p>
            ) : null}
          </div>
        )}
      </SheetModal>
      <Dialog
        open={dismissing}
        onOpenChange={setDismissing}
        title={C.dismissTitle}
        action={
          <Button
            variant="primary"
            size="sm"
            disabled={reason === null || dismiss.isPending || selected === undefined}
            onClick={() => {
              if (reason === null || selected === undefined) return;
              dismiss.mutate({
                path: { opportunity_id: selected.opportunity_id },
                body: { reason },
              } as never);
            }}
          >
            {C.dismissConfirm}
          </Button>
        }
      >
        <fieldset className="flex flex-col gap-[6px] text-[13px]">
          <legend className="pb-[6px] text-ink-2">{C.reasonLabel}</legend>
          {(Object.keys(C.reasons) as Reason[]).map((r) => (
            <label key={r} className="flex items-center gap-[8px]">
              <input
                type="radio"
                name="reason"
                checked={reason === r}
                onChange={() => {
                  setReason(r);
                }}
              />
              {C.reasons[r]}
            </label>
          ))}
        </fieldset>
      </Dialog>
    </div>
  );
}

function Card({
  label,
  value,
  children,
}: {
  label: string;
  value?: string;
  children?: JSX.Element;
}): JSX.Element {
  return (
    <div className="flex h-[44px] min-w-[150px] flex-col justify-center rounded-[10px] bg-card px-[12px] shadow-e1">
      <span className="text-[11px] text-ink-3 uppercase">{label}</span>
      {value === undefined ? children : <span className="text-[15px] tabular-nums">{value}</span>}
    </div>
  );
}

function Kv({ k, children }: { k: string; children: React.ReactNode }): JSX.Element {
  return (
    <div className="flex min-h-[44px] items-center justify-between gap-[12px] px-[14px] hairline-b">
      <dt className="w-[300px] text-[13px] text-ink-2">{k}</dt>
      <dd className="text-right text-[13px]">{children}</dd>
    </div>
  );
}

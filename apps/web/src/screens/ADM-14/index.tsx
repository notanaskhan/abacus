// ADM-14 · Plan & usage (G-04-T18, DEC-5639; handoff ADM-14 a to f; SPEC-681): /settings/plan on
// the T12 settings frame. The meter, the service-line rows, the alerts, the engagement budget, the
// seats, the billing rates and the modules are the server's (`/v1/firm/plan`, `/usage`,
// `/budget-alerts`, `/engagement-budgets`, `/billing-rates`); the browser formats and draws the
// bar, and never totals a figure. Save stays disabled until an alert setting changes; a partner
// reads the page with every band locked and Request more… still enabled (ADM-14 e). Overage shows
// no amount (P-27).
import type { BudgetAlertsOut, PlanRequestIn } from "@abacus/api-client";
import {
  billingRatesOptions,
  budgetAlertsGetOptions,
  budgetAlertsGetQueryKey,
  budgetAlertsPutMutation,
  engagementBudgetsOptions,
  firmUsageOptions,
  planGetOptions,
  planRequestsCreateMutation,
  settingsOverviewOptions,
} from "@abacus/api-client/query";
import {
  Button,
  DEFAULT_TZ,
  Dialog,
  Fieldset,
  Pill,
  SettingsLayout,
  SettingsLock,
  Skeleton,
  Toggle,
  ValueRow,
  amount,
  date,
  pct,
  toast,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { useNow } from "../../app-core/clock";
import { GROUPS } from "../ADM-01/copy";
import { COPY as C } from "./copy";

export interface ADM14Props {
  /** A partner reads the page: every band locked, Request more… enabled (ADM-14 e). */
  readOnly?: boolean;
  initial?: { requestOpen?: boolean; at100?: "keep_running" | "pause_scheduled" };
  onNavigate?: (section: string) => void;
  onBack?: () => void;
}

const n = (v: number): string => amount(String(v), "whole").text;
const DAY_MS = 86_400_000;

function Meter({ used, included }: { used: number; included: number }): JSX.Element {
  // The bar's geometry only: the share is drawn, never printed from here.
  const share = included === 0 ? 0 : used / included;
  const fill = Math.min(share, 1) * 100;
  const tone = share > 1 ? "bg-red-ink" : share >= 0.9 ? "bg-amber-ink" : "bg-ink";
  return (
    <div className="relative mt-[8px] h-[8px] rounded-pill bg-hair" aria-hidden="true">
      <div className={`h-full rounded-pill ${tone}`} style={{ width: `${String(fill)}%` }} />
      {[75, 90, 100].map((t) => (
        <span
          key={t}
          className="absolute top-[-3px] h-[14px] w-px bg-ink-3"
          style={{ left: `${String(t)}%` }}
        />
      ))}
    </div>
  );
}

function pctText(used: number, included: number): string {
  // Display rounding of the server's two integers (one decimal, as the artboards print it).
  return pct(String(included === 0 ? 0 : used / included), { decimals: 1 });
}

export function ADM14({
  readOnly = false,
  initial = {},
  onNavigate,
  onBack,
}: ADM14Props): JSX.Element {
  const now = useNow();
  const qc = useQueryClient();
  const overview = useQuery({ ...settingsOverviewOptions(), retry: false });
  const plan = useQuery(planGetOptions());
  const usage = useQuery(firmUsageOptions());
  const alerts = useQuery(budgetAlertsGetOptions());
  const budgets = useQuery(engagementBudgetsOptions());
  const rates = useQuery(billingRatesOptions());
  const [at100, setAt100] = useState<BudgetAlertsOut["at_100_behaviour"] | undefined>(
    initial.at100,
  );
  const [requestOpen, setRequestOpen] = useState(initial.requestOpen === true);
  const [reason, setReason] = useState("");
  const [seatsTo, setSeatsTo] = useState<string>("");
  const save = useMutation({
    ...budgetAlertsPutMutation(),
    onSuccess: () => {
      setAt100(undefined);
      void qc.invalidateQueries({ queryKey: budgetAlertsGetQueryKey() });
      toast.show(C.saved);
    },
  });
  const request = useMutation({
    ...planRequestsCreateMutation(),
    onSuccess: () => {
      setRequestOpen(false);
    },
  });

  const onSave = (): void => {
    if (a === undefined || at100 === undefined) return;
    save.mutate({
      body: {
        version: a.version,
        at_100_behaviour: at100,
        engagement_default_minutes: a.engagement_default_minutes,
        rules: a.rules.map((r) => ({
          enabled: r.enabled,
          threshold_pct: r.threshold_pct,
          recipient_groups: r.recipient_groups,
          recipient_user_ids: r.recipients.map((x) => x.user_id),
        })),
      },
    });
  };

  const p = plan.data;
  const u = usage.data;
  const a = alerts.data;
  const fmt = (iso: string, withYear = false): string =>
    date(iso, { tz: DEFAULT_TZ, now, withYear });
  const dirty = at100 !== undefined && a !== undefined && at100 !== a.at_100_behaviour;
  const lock = readOnly ? { action: <SettingsLock /> } : {};

  const body = ((): JSX.Element => {
    if (p === undefined || u === undefined || a === undefined) {
      return <Skeleton aria-label={C.title} className="h-[600px] w-full" />;
    }
    const included = u.included_minutes;
    const used = u.used_minutes;
    const next = a.rules.find((r) => r.enabled && r.threshold_minutes > used);
    const reset = u.ends_on ? fmt(new Date(Date.parse(u.ends_on) + DAY_MS).toISOString()) : "";
    const over = used - included;
    const behaviour = at100 ?? a.at_100_behaviour;
    const granite = budgets.data?.items[0];
    return (
      <div className="grid grid-cols-2 gap-[12px] p-[12px]">
        <div className="flex flex-col gap-[12px]">
          <Fieldset title={C.minutes.title} {...lock}>
            <div data-adm14="meter" className="px-[12px] py-[10px]">
              <div className="flex items-baseline justify-between">
                <span>
                  <span className="text-[22px] font-medium tabular-nums">{n(used)}</span>
                  <span className="text-[13px] text-ink-2">{C.minutes.of(n(included))}</span>
                </span>
                <span className="text-[13px] font-medium">{pctText(used, included)}</span>
              </div>
              <Meter used={used} included={included} />
              <p className="mt-[8px] text-[11.5px] text-ink-3">
                {over > 0
                  ? C.minutes.over(n(over))
                  : next
                    ? C.minutes.nextAlert(
                        next.threshold_pct,
                        n(next.threshold_minutes),
                        n(next.threshold_minutes - used),
                        reset,
                      )
                    : C.minutes.left(n(included - used), reset)}
              </p>
            </div>
            {u.by_service_line.length > 0 ? (
              <>
                <div className="h-[28px] bg-nested px-[12px] text-[12px] leading-[28px] text-ink-2">
                  {C.minutes.byLine}
                </div>
                {u.by_service_line.map((l) => (
                  <ValueRow key={l.key} kind="value" label={l.label}>
                    <span className="tabular-nums">{n(l.minutes)}</span>
                  </ValueRow>
                ))}
              </>
            ) : null}
          </Fieldset>
          <Fieldset title={C.alerts.title} {...lock}>
            {a.rules.map((r, i) => (
              <div
                key={r.id}
                data-adm14="rule"
                className="flex items-center justify-between px-[12px] py-[6px]"
              >
                <div>
                  <div className="text-[13px] text-ink-2">
                    {C.alerts.rule(r.threshold_pct, n(r.threshold_minutes), i === 0)}
                  </div>
                  <div className="text-[11.5px] text-ink-3">
                    {r.recipients.length > 0
                      ? r.recipients.map((x) => x.display_name).join(", ")
                      : C.alerts.groups}
                  </div>
                </div>
                <Toggle
                  checked={r.enabled}
                  disabled={readOnly}
                  label={C.alerts.rule(r.threshold_pct, n(r.threshold_minutes), i === 0)}
                />
              </div>
            ))}
            <ValueRow
              kind="select"
              label={C.alerts.at100}
              readOnly={readOnly}
              value={behaviour === "keep_running" ? C.alerts.keep : C.alerts.pause}
              options={[
                { value: C.alerts.keep, label: C.alerts.keep },
                { value: C.alerts.pause, label: C.alerts.pause },
              ]}
              onChange={(v) => {
                setAt100(v === C.alerts.pause ? "pause_scheduled" : "keep_running");
              }}
            />
            <div className="h-[28px] bg-nested px-[12px] text-[12px] leading-[28px] text-ink-2">
              {C.alerts.engagement}
            </div>
            <ValueRow kind="value" label={C.alerts.defaultBudget}>
              {C.alerts.perMonth(n(a.engagement_default_minutes))}
            </ValueRow>
            <p className="px-[12px] pb-[6px] text-[11.5px] text-ink-3">
              {C.alerts.defaultHelp(a.engagement_alert_pct)}
            </p>
            {granite ? (
              <ValueRow kind="value" label={granite.engagement_name}>
                <span className="flex items-center gap-[6px]">
                  {C.alerts.budgetRow(
                    n(granite.used_minutes),
                    n(granite.budget_minutes),
                    granite.used_pct,
                  )}
                  {granite.alert_sent_at ? (
                    <Pill variant="amber">
                      {C.alerts.sent(
                        fmt(granite.alert_sent_at),
                        granite.alert_sent_to_initials ?? "",
                      )}
                    </Pill>
                  ) : null}
                </span>
              </ValueRow>
            ) : null}
          </Fieldset>
        </div>
        <div className="flex flex-col gap-[12px]">
          <Fieldset title={C.seats.title} {...lock}>
            <ValueRow kind="value" label={C.seats.term}>
              {C.seats.annual(fmt(p.term_start), fmt(p.term_end, true))}
            </ValueRow>
            <ValueRow kind="value" label={C.seats.renewal}>
              {C.seats.inDays(fmt(p.renewal_on, true), p.renewal_in_days)}
            </ValueRow>
            <ValueRow kind="value" label={C.seats.contact}>
              {p.billing_contact?.display_name ?? ""}
            </ValueRow>
            <ValueRow kind="value" label={C.seats.seats}>
              <span className="flex items-center gap-[6px]">
                {C.seats.used(p.seats.used, p.seats.total)}
                {p.seats.full ? <Pill variant="amber">{C.seats.full}</Pill> : null}
              </span>
            </ValueRow>
            {p.seats.full ? (
              <p className="px-[12px] pb-[6px] text-[11.5px] text-ink-3">{C.seats.fullHelp}</p>
            ) : null}
            <ValueRow kind="value" label={C.seats.workbench}>
              {C.seats.active(p.workbench_active_30d, p.seats.total)}
            </ValueRow>
          </Fieldset>
          <Fieldset title={C.rates.title} action={<SettingsLock />}>
            {rates.data?.connected ? (
              <>
                {rates.data.bands.map((b) => (
                  <ValueRow key={b.label} kind="value" label={C.rates.band(b.label, b.people)}>
                    {b.hourly_rate === null ? (
                      <span className="text-ink-3">{C.rates.nonChargeable}</span>
                    ) : (
                      C.rates.perHour(amount(b.hourly_rate, "dollars").text)
                    )}
                  </ValueRow>
                ))}
                {rates.data.effective_from ? (
                  <p className="px-[12px] pb-[6px] text-[11.5px] text-ink-3">
                    {C.rates.effective(fmt(rates.data.effective_from, true))}
                  </p>
                ) : null}
              </>
            ) : (
              <p className="px-[12px] py-[8px] text-[12.5px] text-ink-3">{C.rates.notConnected}</p>
            )}
          </Fieldset>
          <Fieldset title={C.modules.title} {...lock}>
            <div className="flex flex-wrap gap-[6px] px-[12px] py-[10px]">
              {p.modules.map((m) => (
                <span
                  key={m}
                  className="rounded-tag bg-nested px-[8px] py-[3px] text-[11.5px] font-medium text-ink-2"
                >
                  {C.modules.names[m] ?? m}
                </span>
              ))}
            </div>
            <ValueRow kind="value" label={C.modules.library}>
              {C.modules.stable}
            </ValueRow>
            <p className="px-[12px] pb-[6px] text-[11.5px] text-ink-3">{C.modules.help}</p>
          </Fieldset>
        </div>
      </div>
    );
  })();

  return (
    <>
      <SettingsLayout
        bare
        wide
        toolbar={{ nav: [], active: "", firm: "" }}
        title={C.firmSettings}
        context={overview.data?.firm_name ?? ""}
        backLabel={C.back}
        {...(onBack ? { onBack } : {})}
        navTitle={C.settings}
        groups={GROUPS}
        active="plan-usage"
        onSelect={(id) => {
          if (id !== "plan-usage") onNavigate?.(id);
        }}
        dirty={dirty}
        readOnly={readOnly}
        readOnlyText={C.readOnly}
        headerActions={
          <span className="flex items-center gap-[8px]">
            <Button
              variant="secondary"
              onClick={() => {
                setRequestOpen(true);
              }}
            >
              {C.requestMore}
            </Button>
            {readOnly ? null : (
              <>
                {dirty ? <span className="text-body text-ink-3">{C.unsaved}</span> : null}
                <Button
                  variant="ghost"
                  size="lg"
                  disabled={!dirty}
                  onClick={() => {
                    setAt100(undefined);
                  }}
                >
                  {C.discard}
                </Button>
                <Button size="lg" disabled={!dirty || save.isPending} onClick={onSave}>
                  {C.save}
                </Button>
              </>
            )}
          </span>
        }
      >
        <div data-screen="ADM-14">{body}</div>
      </SettingsLayout>
      <Dialog
        open={requestOpen}
        onOpenChange={setRequestOpen}
        title={C.request.title}
        action={
          <Button
            variant="primary"
            disabled={reason.trim() === ""}
            onClick={() => {
              const input: PlanRequestIn = {
                kind: "seats",
                reason: reason.trim(),
                to_value: Number(seatsTo || p?.seats.total || 0),
              };
              request.mutate({
                headers: { "Idempotency-Key": `adm14-${crypto.randomUUID()}` },
                body: input,
              });
            }}
          >
            {C.request.send}
          </Button>
        }
      >
        <div data-adm14="request" className="flex flex-col gap-[8px] p-[16px] text-[13px]">
          <label className="flex items-center justify-between gap-[8px]">
            <span className="text-ink-2">{C.request.seats}</span>
            <input
              type="number"
              min={p?.seats.total ?? 0}
              value={seatsTo === "" ? String(p?.seats.total ?? "") : seatsTo}
              onChange={(e) => {
                setSeatsTo(e.target.value);
              }}
              className="h-[30px] w-[96px] rounded-input bg-card px-[8px] text-right inset-ring-[0.5px] inset-ring-stroke"
            />
          </label>
          <label className="flex flex-col gap-[4px]">
            <span className="text-ink-2">{C.request.reason}</span>
            <textarea
              value={reason}
              maxLength={2000}
              onChange={(e) => {
                setReason(e.target.value);
              }}
              className="min-h-[72px] rounded-input bg-card p-[8px] inset-ring-[0.5px] inset-ring-stroke"
            />
          </label>
          {a?.partner_approver ? (
            <p className="text-[12.5px] text-ink-3">
              {C.request.approval(a.partner_approver.display_name)}
            </p>
          ) : null}
        </div>
      </Dialog>
    </>
  );
}

import type { Aud27ItemOut, Aud27ListOut, Aud27ProhibitedOut } from "@abacus/api-client";
import {
  estimatesOptions,
  partiesInInterestOptions,
  relatedPartiesOptions,
} from "@abacus/api-client/query";
import {
  type CockpitCanvas,
  type ViewState,
  Button,
  PaneAction,
  Pill,
  Segmented,
  StatusPill,
  amount,
  cn,
  status,
} from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { useFlag } from "../../app-core/flags";
import { COPY } from "./copy";

// AUD-27 · Estimates, related parties & parties in interest (A-05-T57; A-05 §4.10; the handoff
// spec): the Fieldwork › Estimates & Related Parties canvas in the T2 cockpit. Every figure is the
// server's (A-05-T53's engine: footing, rollforward, retrospective, range, bias). Status words are
// the registry's `aud27_item` only (Unevaluated, Evaluated, Exception, muted Screened out); the
// agent never concludes: the conclusion is the EP's card (SHL-11), an exception a person's (SHL-15).

export const ESTIMATES_RP = "estimates_rp";
const FLAG = "assurance.estimates_rp";
export type Aud27Tab = keyof typeof COPY.tabs;
export type EngagementKind = "fs" | "ebp";
const TABS: Record<EngagementKind, readonly Aud27Tab[]> = {
  fs: ["estimates", "related_parties"],
  ebp: ["related_parties", "parties_in_interest"],
};
const CARD = "rounded-[12px] bg-card e1 p-[12px]";
const TH = "h-[30px] px-[8px] text-left text-[11.5px] font-medium text-ink-3";
const TD = "h-[34px] px-[8px] text-[12.5px] align-middle";

const money = (v: string | null | undefined): string =>
  v === null || v === undefined ? COPY.estimates.none : amount(v, "money").text;

function Status({ item }: { item: Aud27ItemOut }): JSX.Element {
  const word = status("aud27_item", item.status, item.pending_ep ? { context: "pending_ep" } : {});
  return (
    <StatusPill variant={word.variant ?? "neutral"} size="state">
      {word.label}
    </StatusPill>
  );
}

export interface EstimatesOptions {
  active?: boolean;
  kind?: EngagementKind;
  tab?: Aud27Tab;
  onTab?: (tab: Aud27Tab) => void;
  onSignOff?: () => void;
  onSourceDocs?: () => void;
  /** Any amount opens SHL-09 with its sources. */
  onAmount?: (itemId: string) => void;
  /** "Request partner conclusion…": SHL-11, reserved to the engagement partner. */
  onRequestConclusion?: (estimateId: string) => void;
  /** "Ask management" opens POR-05's inquiry draft; a person sends it. */
  onAskManagement?: (partyId: string) => void;
  /** "Raise exception…" opens SHL-15. */
  onRaise?: (itemId: string) => void;
  /** A finding link opens AUD-15; a disclosure chip AUD-20; a schedule reference EBP-07. */
  onReference?: (screen: "AUD-15" | "AUD-20" | "EBP-07", id?: string) => void;
}

function EstimatesTable({
  items,
  selected,
  onSelect,
  onAmount,
}: {
  items: readonly Aud27ItemOut[];
  selected: string | null;
  onSelect: (id: string) => void;
  onAmount: ((id: string) => void) | undefined;
}): JSX.Element {
  return (
    <section data-aud27="estimates" className={CARD}>
      <h3 className="mb-[6px] text-[13px] font-medium">{COPY.estimates.card}</h3>
      <table className="w-full border-collapse">
        <thead>
          <tr>
            {COPY.estimates.columns.map((c) => (
              <th key={c} scope="col" className={TH}>
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {items.map((e) => {
            const retro = e.retrospectives?.[0];
            return (
              <tr
                key={e.id}
                data-estimate={e.id}
                {...(selected === e.id ? { "data-selected": "" } : {})}
                onClick={() => {
                  onSelect(e.id);
                }}
                className={cn(
                  "cursor-pointer hairline-t",
                  selected === e.id && "bg-tonal-selected",
                )}
              >
                <td className={TD}>
                  <span className="flex items-center gap-[6px]">
                    {e.name}
                    {e.significant_risk === true && (
                      <Pill variant="red-tint" size="micro">
                        {COPY.estimates.significantRisk}
                      </Pill>
                    )}
                  </span>
                </td>
                <td className={cn(TD, "tabular-nums")}>
                  <button
                    type="button"
                    data-amount={e.id}
                    onClick={(event) => {
                      event.stopPropagation();
                      onAmount?.(e.id);
                    }}
                  >
                    {money(e.amount)}
                  </button>
                </td>
                <td className={cn(TD, "text-ink-2")}>{e.method_text ?? COPY.estimates.none}</td>
                <td className={cn(TD, "tabular-nums text-ink-2")}>
                  {retro === undefined ? (
                    COPY.estimates.none
                  ) : (
                    <>
                      {COPY.estimates.vs(money(retro.prior_estimate), money(retro.outcome))}{" "}
                      <span className="text-ink-3">
                        (
                        {(retro.direction === "under"
                          ? COPY.estimates.under
                          : COPY.estimates.over)(
                          money(retro.difference.replace("-", "")),
                          retro.percent,
                        )}
                        )
                      </span>
                    </>
                  )}
                </td>
                <td className={cn(TD, "tabular-nums")}>
                  {e.range == null
                    ? COPY.estimates.none
                    : COPY.estimates.range(money(e.range.low), money(e.range.high))}
                </td>
                <td className={TD}>
                  <Status item={e} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}

function MethodCard({ e }: { e: Aud27ItemOut }): JSX.Element {
  const components = e.components ?? [];
  return (
    <section data-aud27="method" className={CARD}>
      <h3 className="mb-[6px] text-[13px] font-medium">{COPY.method.card(e.name)}</h3>
      <table className="w-full border-collapse">
        <tbody>
          {components.map((c) => (
            <tr key={c.label} className="hairline-t">
              <td className={TD}>{c.label}</td>
              <td className={cn(TD, "text-right tabular-nums")}>{money(c.amount)}</td>
            </tr>
          ))}
          {e.method != null && (
            <tr data-row="total" className="hairline-t font-medium">
              <td className={TD}>{COPY.method.total}</td>
              <td className={cn(TD, "text-right tabular-nums")}>
                {money(e.method.components_total)}
                {e.account_ref != null && (
                  <span
                    data-tie={e.method.ties ? "ties" : "off"}
                    className="ml-[8px] text-[11px] font-normal text-ink-3"
                  >
                    {COPY.method.tieTo(e.account_ref)}
                  </span>
                )}
              </td>
            </tr>
          )}
        </tbody>
      </table>
      {e.rollforward != null && (
        <p data-aud27="rollforward" className="mt-[8px] text-[12.5px] tabular-nums text-ink-2">
          {COPY.method.rollforward(
            money(e.rollforward.opening),
            money(e.rollforward.usage),
            money(e.rollforward.additions),
            money(e.rollforward.computed_closing),
          )}
        </p>
      )}
    </section>
  );
}

function BiasCard({ e }: { e: Aud27ItemOut }): JSX.Element | null {
  if (e.bias == null) return null;
  const retros = e.retrospectives ?? [];
  const ceiling = String(Math.ceil(Math.max(0, ...retros.map((r) => Number(r.percent)))));
  return (
    <section data-aud27="bias" data-bias={e.bias} className={CARD}>
      <h3 className="mb-[4px] text-[13px] font-medium">{COPY.bias.card}</h3>
      <p className="text-[12.5px] text-ink-2">
        {e.bias === "none" ? COPY.bias.none(retros.length, ceiling) : COPY.bias.possible}
      </p>
    </section>
  );
}

function DisclosureCard({
  e,
  onReference,
}: {
  e: Aud27ItemOut;
  onReference: EstimatesOptions["onReference"];
}): JSX.Element | null {
  if (e.disclosure_ref == null) return null;
  return (
    <section data-aud27="disclosure" className={CARD}>
      <h3 className="mb-[4px] text-[13px] font-medium">{COPY.disclosure.card}</h3>
      <span className="flex items-center gap-[8px] text-[12.5px]">
        <button type="button" onClick={() => onReference?.("AUD-20")}>
          {e.disclosure_ref}
        </button>
        <Pill variant="green-tint" size="micro">
          {COPY.disclosure.linked}
        </Pill>
      </span>
    </section>
  );
}

function RelatedTable({
  items,
  options,
}: {
  items: readonly Aud27ItemOut[];
  options: EstimatesOptions;
}): JSX.Element {
  return (
    <section data-aud27="related_parties" className={CARD}>
      <table className="w-full border-collapse">
        <thead>
          <tr>
            {COPY.related.columns.map((c) => (
              <th key={c} scope="col" className={TH}>
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {items.map((p) => (
            <tr key={p.id} data-party={p.id} data-status={p.status} className="hairline-t">
              <td className={TD}>{p.name}</td>
              <td className={cn(TD, "text-ink-2")}>{p.relationship ?? COPY.estimates.none}</td>
              <td className={cn(TD, "text-ink-2")}>
                {COPY.related.source[p.source ?? ""] ?? COPY.estimates.none}
              </td>
              <td className={TD}>
                <span className="flex items-center gap-[8px]">
                  <Status item={p} />
                  {p.status === "exception" && p.finding_id == null && (
                    <>
                      <button
                        type="button"
                        data-action="ask"
                        className="text-[12px] text-ink-2 underline"
                        onClick={() => options.onAskManagement?.(p.id)}
                      >
                        {COPY.related.askManagement}
                      </button>
                      <Button
                        variant="secondary"
                        size="xs"
                        onClick={() => options.onRaise?.(p.id)}
                      >
                        {COPY.related.raise}
                      </Button>
                    </>
                  )}
                  {p.finding_id != null && (
                    <button
                      type="button"
                      data-action="finding"
                      className="text-[12px] text-ink-2 underline"
                      onClick={() => options.onReference?.("AUD-15", p.finding_id ?? undefined)}
                    >
                      {COPY.related.finding}
                    </button>
                  )}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function PartiesTable({
  view,
  options,
}: {
  view: Aud27ListOut;
  options: EstimatesOptions;
}): JSX.Element {
  const prohibited: readonly Aud27ProhibitedOut[] = view.prohibited ?? [];
  return (
    <>
      <section data-aud27="parties_in_interest" className={CARD}>
        <table className="w-full border-collapse">
          <thead>
            <tr>
              {COPY.pii.columns.map((c) => (
                <th key={c} scope="col" className={TH}>
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {view.items.map((p) => (
              <tr key={p.id} data-party={p.id} data-status={p.status} className="hairline-t">
                <td className={TD}>{p.name}</td>
                <td className={cn(TD, "text-ink-2")}>{p.relationship}</td>
                <td className={cn(TD, "text-ink-2")}>{p.exemption ?? COPY.estimates.none}</td>
                <td className={TD}>
                  <span className="flex items-center gap-[8px]">
                    <button type="button" onClick={() => options.onReference?.("EBP-07")}>
                      {p.reporting ?? COPY.estimates.none}
                    </button>
                    {p.status === "exception" && <Status item={p} />}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      {prohibited.map((t) => (
        <section key={t.late_remittance_id} data-aud27="prohibited" className={CARD}>
          <h3 className="mb-[6px] text-[13px] font-medium">{COPY.pii.card}</h3>
          <dl className="grid grid-cols-[160px_1fr] gap-y-[4px] text-[12.5px]">
            <dt className="text-ink-3">{COPY.pii.lostEarnings}</dt>
            <dd className="tabular-nums">{money(t.lost_earnings)}</dd>
            <dt className="text-ink-3">{COPY.pii.correction}</dt>
            <dd>{t.correction_status ?? COPY.estimates.none}</dd>
            <dt className="text-ink-3">{COPY.pii.form5330}</dt>
            <dd>{t.form_5330_status ?? COPY.estimates.none}</dd>
            <dt className="text-ink-3">{COPY.pii.scheduleG}</dt>
            <dd>{COPY.pii.scheduleGNote}</dd>
          </dl>
        </section>
      ))}
    </>
  );
}

export function useEstimatesCanvas(
  workItemId: string,
  options: EstimatesOptions = {},
): CockpitCanvas {
  const on = useFlag(FLAG) === true;
  const enabled = options.active !== false && on;
  const kind = options.kind ?? "fs";
  const tabs = TABS[kind];
  const path = { work_item_id: workItemId };
  const [localTab, setLocalTab] = useState<Aud27Tab>(tabs[0] ?? "estimates");
  const tab = options.tab ?? localTab;
  const [selected, setSelected] = useState<string | null>(null);
  const estimates = useQuery({
    ...estimatesOptions({ path }),
    enabled: enabled && tab === "estimates",
    retry: false,
  });
  const related = useQuery({
    ...relatedPartiesOptions({ path }),
    enabled: enabled && tab === "related_parties",
    retry: false,
  });
  const parties = useQuery({
    ...partiesInInterestOptions({ path }),
    enabled: enabled && tab === "parties_in_interest",
    retry: false,
  });
  const items = estimates.data?.items ?? [];
  const current =
    items.find((e) => e.id === selected) ?? items.find((e) => e.pending_ep) ?? items[0];
  const relatedCount = (related.data?.items ?? []).filter(
    (p) => p.status === "exception" || p.status === "unevaluated",
  ).length;
  const query = tab === "estimates" ? estimates : tab === "related_parties" ? related : parties;
  const signOff = options.onSignOff === undefined ? {} : { onClick: options.onSignOff };
  const source = options.onSourceDocs === undefined ? {} : { onClick: options.onSourceDocs };
  let state: ViewState = { kind: "ready" };
  if (!on) state = { kind: "flag-off", flag: "assurance.estimates_rp" };
  else if (query.isError) {
    const code = (query.error as { status?: number } | null)?.status;
    state =
      code === 404
        ? { kind: "restricted", reason: "walled" }
        : { kind: "error", retry: () => void query.refetch() };
  } else if (query.data === undefined) state = { kind: "loading" };
  const label = (t: Aud27Tab): string =>
    t === "related_parties" && relatedCount > 0
      ? `${COPY.tabs[t]} ${String(relatedCount)}`
      : COPY.tabs[t];
  return {
    title: COPY.title,
    well: true,
    state,
    actions: (
      <>
        <PaneAction label={COPY.edit} />
        <PaneAction label={COPY.signOff} {...signOff} />
        <PaneAction label={COPY.sourceDocs} {...source} />
      </>
    ),
    controls: (
      <div className="flex w-full items-center justify-between">
        <Segmented
          label={COPY.title}
          active={label(tab)}
          onChange={(picked) => {
            const next = tabs.find((t) => label(t) === picked);
            if (next !== undefined) {
              setLocalTab(next);
              options.onTab?.(next);
            }
          }}
          options={tabs.map(label)}
        />
        <PaneAction label={COPY.openInExcel} />
      </div>
    ),
    footer:
      tab === "estimates" && current !== undefined && current.status === "evaluated" ? (
        <div className="flex items-center gap-[8px]">
          <Button
            variant="primary"
            size="sm"
            onClick={() => options.onRequestConclusion?.(current.id)}
          >
            {COPY.requestConclusion}
          </Button>
        </div>
      ) : undefined,
    children: (
      <div data-aud27-tab={tab} className="flex flex-col gap-[10px] p-[10px]">
        {tab === "estimates" && (
          <>
            <EstimatesTable
              items={items}
              selected={current?.id ?? null}
              onSelect={setSelected}
              onAmount={options.onAmount}
            />
            {current !== undefined && current.status !== "unevaluated" && (
              <>
                <MethodCard e={current} />
                <BiasCard e={current} />
                <DisclosureCard e={current} onReference={options.onReference} />
              </>
            )}
          </>
        )}
        {tab === "related_parties" && related.data !== undefined && (
          <RelatedTable items={related.data.items} options={options} />
        )}
        {tab === "parties_in_interest" && parties.data !== undefined && (
          <PartiesTable view={parties.data} options={options} />
        )}
      </div>
    ),
  };
}

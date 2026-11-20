// CLS-09 · Close plan editor (C-01-T36; handoff CLS-09 a, a2, a3, b, b2, c, d, e, f; SPEC-655
// AC-15 to AC-22): T6 control bar · tally strip · full-width plan table. The plan is the client's
// newest version (`GET /v1/clients/{id}/close-plan`): published read-only until Edit plan (a), a
// draft with its changed cells (b), a Close Planner draft whose rows carry an outlined tick until a
// person adopts each (c). The tallies are the version's own (`tally`), so an edit reflows them;
// the browser counts only the accounts it lists. Publish is the matrix's (`allowed_actions`): a
// Manager or Partner publishes (b2, with the confirm), a Senior requests it. A row's hover shows
// its label-over-value card (a2); a click opens the O2 drawer (a3) whose values take pickers while
// the plan is a draft. No plan yet (d): the firm's templates and Draft from ledger history.
// Requests (e) and History (f) are the version's request templates and the version list.
import type { PlanRowOut, PlanVersionOut } from "@abacus/api-client";
import {
  adoptPlanRowMutation,
  closePlanHistoryOptions,
  closePlanOptions,
  closePlanQueryKey,
  closeTemplatesOptions,
  createPlanDraftMutation,
  draftPlanFromHistoryMutation,
  getClientOptions,
  patchPlanRowMutation,
  publishPlanMutation,
  requestPlanPublishMutation,
} from "@abacus/api-client/query";
import {
  Button,
  ConfirmDialog,
  Drawer,
  EmptyState,
  Icon,
  Menu,
  Picker,
  ProgressBar,
  SearchField,
  Segmented,
  Skeleton,
  TallyStrip,
  Tag,
  ViewStateBody,
  date,
  isoDate,
  monthYear,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useMemo, useState } from "react";
import { useNow } from "../../app-core/clock";
import { isNotFound } from "../../domain/audits";
import { closeReadState } from "../../domain/closes";
import { COPY, FREQUENCY, PROCEDURE, REVIEW, SOURCE, fill } from "./copy";

export type PlanTab = "plan" | "requests" | "history";
export type Grouping = "class" | "procedure";

export interface CLS09Props {
  clientId: string;
  clientName?: string;
  /** A scenario's starting surfaces (a2 hover, a3 drawer, b2 publish confirm, c drafting, e, f). */
  initial?: {
    tab?: PlanTab;
    grouping?: Grouping;
    hover?: number;
    drawer?: number;
    publishOpen?: boolean;
    drafting?: { done: number; total: number; requestedBy: string; at: string };
  };
  onBack?: () => void;
}

const INCOME_STATEMENT = "Income Statement";

/** CLS-09's ACCOUNTS: the balance-sheet accounts the plan lists (the income statement's two
 * procedures run over every revenue and expense account, so they are not counted). */
export function accountsOf(rows: readonly PlanRowOut[]): number {
  return new Set(
    rows.filter((r) => r.account_class !== INCOME_STATEMENT).map((r) => r.account_name),
  ).size;
}

/** Rows grouped in plan order: by account class (the statement grammar) or by procedure. */
export function groupsOf(
  rows: readonly PlanRowOut[],
  grouping: Grouping,
): { key: string; rows: PlanRowOut[] }[] {
  const out = new Map<string, PlanRowOut[]>();
  for (const r of [...rows].sort((a, b) => a.position - b.position)) {
    const key = grouping === "class" ? r.account_class : PROCEDURE[r.procedure];
    out.set(key, [...(out.get(key) ?? []), r]);
  }
  return [...out].map(([key, rs]) => ({ key, rows: rs }));
}

function changesOf(plan: PlanVersionOut): number {
  return plan.rows.filter((r) => r.changed_from_previous === true).length;
}

function can(plan: PlanVersionOut, action: string): boolean {
  return (plan.allowed_actions ?? []).includes(action as never);
}

function Card({
  row,
  edit,
  onPatch,
}: {
  row: PlanRowOut;
  edit: boolean;
  onPatch?: (patch: Partial<PlanRowOut>) => void;
}): JSX.Element {
  const line = (label: string, value: string, picker?: JSX.Element): JSX.Element => (
    <div className="flex min-h-[48px] flex-col justify-center border-b border-hair px-[14px] py-[6px] last:border-b-0">
      <span className="text-[11.5px] text-ink-3">{label}</span>
      {edit && picker !== undefined ? picker : <span className="text-[13px]">{value}</span>}
    </div>
  );
  const pick = (
    key: "procedure" | "source" | "review_level" | "frequency",
    labels: Record<string, string>,
    label: string,
  ): JSX.Element => (
    <Picker
      label={label}
      variant="white"
      value={row[key]}
      options={Object.entries(labels).map(([value, text]) => ({ value, label: text }))}
      onChange={(value) => onPatch?.({ [key]: value })}
    />
  );
  return (
    <div data-plan-card={row.row_id} className="rounded-card bg-card shadow-e1">
      {line(
        PROCEDURE[row.procedure],
        row.method,
        pick("procedure", PROCEDURE, COPY.columns.procedure),
      )}
      {line(COPY.drawer.evidence, row.evidence_required ?? COPY.noThreshold)}
      {line(COPY.drawer.source, SOURCE[row.source], pick("source", SOURCE, COPY.drawer.source))}
      {line(
        COPY.drawer.review,
        REVIEW[row.review_level],
        pick("review_level", REVIEW, COPY.drawer.review),
      )}
      {line(
        COPY.drawer.frequency,
        FREQUENCY[row.frequency],
        pick("frequency", FREQUENCY, COPY.drawer.frequency),
      )}
      {line(COPY.drawer.threshold, row.threshold?.label ?? COPY.noThreshold)}
    </div>
  );
}

function PlanRow({
  row,
  hovered,
  edit,
  onHover,
  onOpen,
  onAdopt,
}: {
  row: PlanRowOut;
  hovered: boolean;
  edit: boolean;
  onHover: (on: boolean) => void;
  onOpen: () => void;
  onAdopt: () => void;
}): JSX.Element {
  const drafted = row.drafted === true && row.adopted !== true;
  const changed = row.changed_from_previous === true;
  return (
    <tr
      data-row={row.row_id}
      data-drafted={drafted ? "" : undefined}
      onMouseEnter={() => {
        onHover(true);
      }}
      onMouseLeave={() => {
        onHover(false);
      }}
      onClick={onOpen}
      className={`relative h-[40px] cursor-pointer text-[12.5px] hover:bg-nested ${hovered ? "bg-nested" : ""}`}
    >
      <td className="px-[12px] py-[6px]">
        <span className="flex items-center gap-[8px]">
          {drafted ? (
            <button
              type="button"
              aria-label={fill(COPY.adopt, { account: row.account_name })}
              data-adopt={row.row_id}
              onClick={(e) => {
                e.stopPropagation();
                onAdopt();
              }}
              className="text-ink-3"
            >
              <Icon name="circle-dashed" size={15} />
            </button>
          ) : null}
          {row.account_name}
        </span>
      </td>
      <td className="px-[8px]">{PROCEDURE[row.procedure]}</td>
      <td className="px-[8px] text-ink-2">{row.method}</td>
      <td className="px-[8px]">{row.evidence_required ?? COPY.noThreshold}</td>
      <td className="px-[8px]">
        {changed && edit ? (
          <span
            data-changed=""
            className="inline-flex items-center gap-[6px] rounded-pill bg-amber-tint px-[6px] text-amber-ink"
          >
            {SOURCE[row.source]}
            <Tag>{COPY.changed}</Tag>
          </span>
        ) : (
          <span className="text-[12px] text-ink-2">{SOURCE[row.source]}</span>
        )}
      </td>
      <td className="px-[8px]">
        <Tag>{REVIEW[row.review_level]}</Tag>
      </td>
      <td className="px-[8px]">{FREQUENCY[row.frequency]}</td>
      <td className="px-[8px]">{row.threshold?.label ?? COPY.noThreshold}</td>
      {hovered ? (
        <td className="absolute left-[260px] top-[38px] z-10 w-[320px]" data-hover-card="">
          <Card row={row} edit={false} />
        </td>
      ) : null}
    </tr>
  );
}

export function CLS09({ clientId, clientName, initial = {}, onBack }: CLS09Props): JSX.Element {
  const now = useNow();
  const queryClient = useQueryClient();
  const path = { client_id: clientId };
  // S48 rest (DV-d): the version stepper (⇕) reads an earlier version; null is the newest.
  const [viewVersion, setViewVersion] = useState<number | null>(null);
  const plan = useQuery({
    ...closePlanOptions({
      path,
      ...(viewVersion === null ? {} : { query: { version: viewVersion } }),
    }),
    retry: false,
  });
  const [stepperOpen, setStepperOpen] = useState(false);
  const versions = useQuery({ ...closePlanHistoryOptions({ path }), enabled: stepperOpen });
  const client = useQuery({ ...getClientOptions({ path }), enabled: clientName === undefined });
  const name = clientName ?? client.data?.name ?? "";
  const [tab, setTab] = useState<PlanTab>(initial.tab ?? "plan");
  const [grouping, setGrouping] = useState<Grouping>(initial.grouping ?? "class");
  const [q, setQ] = useState("");
  const [hover, setHover] = useState<string | null>(null);
  const [drawer, setDrawer] = useState<string | null>(null);
  const [publishOpen, setPublishOpen] = useState(initial.publishOpen ?? false);
  const history = useQuery({ ...closePlanHistoryOptions({ path }), enabled: tab === "history" });
  const empty = plan.isError && isNotFound(plan.error);
  const templates = useQuery({ ...closeTemplatesOptions(), enabled: empty });
  const refresh = (): void => {
    void queryClient.invalidateQueries({ queryKey: closePlanQueryKey({ path }) });
  };
  const createDraft = useMutation({ ...createPlanDraftMutation(), onSuccess: refresh });
  const patch = useMutation({ ...patchPlanRowMutation(), onSuccess: refresh });
  const adopt = useMutation({ ...adoptPlanRowMutation(), onSuccess: refresh });
  const publish = useMutation({ ...publishPlanMutation(), onSuccess: refresh });
  const requestPublish = useMutation({ ...requestPlanPublishMutation(), onSuccess: refresh });
  const draftFromHistory = useMutation({ ...draftPlanFromHistoryMutation(), onSuccess: refresh });

  const data = plan.data;
  const rows = data?.rows ?? [];
  const sorted = useMemo(() => [...rows].sort((a, b) => a.position - b.position), [rows]);
  // A scenario names its hovered or open row by position; the screen keeps the id.
  const hoverId =
    hover ?? (initial.hover === undefined ? null : (sorted[initial.hover]?.row_id ?? null));
  const drawerId =
    drawer ?? (initial.drawer === undefined ? null : (sorted[initial.drawer]?.row_id ?? null));
  const shown = rows.filter(
    (r) => q === "" || r.account_name.toLowerCase().includes(q.toLowerCase()),
  );

  const header = (
    <div className="flex h-[42px] items-center justify-center gap-[6px] text-[15px] font-medium">
      <span>{name}</span>
      <span className="text-ink-3">·</span>
      <span className="font-normal text-ink-2">{COPY.closePlan}</span>
      {data !== undefined ? (
        <>
          <span className="text-ink-3">·</span>
          <span className="font-normal text-ink-2" data-version={data.version}>
            v{data.version}
            {data.status === "draft" ? " · draft" : ""}
          </span>
          <Menu
            label={COPY.versionStepper}
            align="center"
            width={176}
            open={stepperOpen}
            onOpenChange={setStepperOpen}
            trigger={
              <button
                type="button"
                aria-label={COPY.versionStepper}
                data-version-stepper=""
                className="flex items-center text-ink-3"
              >
                <Icon name="chevrons-up-down" size={14} />
              </button>
            }
            sections={[
              [...new Set((versions.data?.items ?? []).map((v) => v.version))]
                .sort((a, b) => b - a)
                .map((v) => ({
                  label: `v${String(v)}`,
                  checked: v === data.version,
                  onSelect: () => {
                    setViewVersion(v);
                  },
                })),
            ]}
          />
        </>
      ) : null}
    </div>
  );

  if (plan.isPending) {
    return (
      <div data-screen-body="CLS-09" className="flex flex-col gap-[10px] p-[12px]">
        {header}
        {Array.from({ length: 8 }, (_, i) => (
          <Skeleton key={i} className="h-[40px] w-full" />
        ))}
      </div>
    );
  }
  if (empty) {
    return (
      <div
        data-screen-body="CLS-09"
        data-state="empty"
        className="flex flex-col items-center gap-[16px] p-[24px]"
      >
        {header}
        <EmptyState icon="clipboard-list" title={COPY.empty.title}>
          {COPY.empty.body}
        </EmptyState>
        <ul className="flex flex-wrap justify-center gap-[12px]">
          {(templates.data?.items ?? []).map((t) => (
            <li
              key={t.template_id}
              data-template={t.key}
              className="flex h-[120px] w-[240px] flex-col justify-end rounded-card bg-card p-[14px] shadow-e1"
            >
              <span className="text-[13px] font-medium">{t.name}</span>
            </li>
          ))}
        </ul>
        <Button
          variant="primary"
          icon="sparkles"
          loading={draftFromHistory.isPending}
          onClick={() => {
            draftFromHistory.mutate({
              path,
              headers: { "Idempotency-Key": crypto.randomUUID() },
            });
          }}
        >
          {COPY.empty.draftFromHistory}
        </Button>
      </div>
    );
  }
  if (data === undefined) {
    // C-01-T42: a refused read (403, the role's notice) or a failed one (Retry); a 404 is the
    // empty plan above.
    const read = closeReadState(plan);
    return (
      <div data-screen-body="CLS-09" data-state={read.kind} className="flex flex-col p-[12px]">
        {header}
        <ViewStateBody state={read} empty={{ title: COPY.closePlan }}>
          {null}
        </ViewStateBody>
      </div>
    );
  }

  const draft = data.status === "draft";
  const agentDraft = draft && rows.some((r) => r.drafted === true);
  const changes = changesOf(data);
  const nextVersion = draft ? data.version : data.version + 1;
  const mayPublish = draft && can(data, "close_plan.publish");
  const mayRequest = draft && !mayPublish && can(data, "close_plan.request_publish");
  const unadopted = rows.filter((r) => r.drafted === true && r.adopted !== true).length;
  const effective = isoDate(now).slice(0, 7);
  const previousMonth = (() => {
    const [y, m] = effective.split("-").map(Number) as [number, number];
    return m === 1 ? `${String(y - 1)}-12` : `${String(y)}-${String(m - 1).padStart(2, "0")}`;
  })();
  const title = agentDraft
    ? fill(COPY.agentDraftTitle, { version: data.version })
    : draft
      ? changes > 0
        ? fill(COPY.draftChanges, {
            version: data.version,
            changes: changes === 1 ? COPY.oneChange : fill(COPY.manyChanges, { n: changes }),
          })
        : fill(COPY.draftTitle, { version: data.version })
      : fill(COPY.planTitle, { version: data.version });
  const meta =
    !draft && data.published_at != null && data.published_by != null
      ? fill(COPY.published, {
          date: date(data.published_at, { now, withYear: true }),
          name: data.published_by.name,
        })
      : agentDraft && initial.drafting !== undefined
        ? fill(COPY.agentDraftMeta, {
            date: date(initial.drafting.at, { now, withYear: true }),
            name: initial.drafting.requestedBy,
          })
        : "";
  const open = rows.find((r) => r.row_id === drawerId) ?? null;
  const patchRow = (row: PlanRowOut, change: Partial<PlanRowOut>): void => {
    patch.mutate({
      path: { client_id: clientId, version: data.version, row_id: row.row_id },
      headers: { "If-Match": String(data.row_version) },
      body: change,
    });
  };

  return (
    <div
      data-screen-body="CLS-09"
      data-state={draft ? "draft" : "published"}
      className="flex min-h-0 flex-1 flex-col"
    >
      {header}
      <div className="relative flex h-[50px] items-center justify-center">
        <button
          type="button"
          onClick={onBack}
          className="absolute left-[12px] flex items-center gap-[4px] text-[13px] text-ink-2"
        >
          <Icon name="chevron-left" size={14} />
          {COPY.back}
        </button>
        <Segmented
          label={COPY.closePlan}
          active={COPY.tabs[tab]}
          options={[
            COPY.tabs.plan,
            { label: COPY.tabs.requests, count: data.tally.requests_per_month },
            COPY.tabs.history,
          ]}
          onChange={(label) => {
            setTab(
              label === COPY.tabs.requests
                ? "requests"
                : label === COPY.tabs.history
                  ? "history"
                  : "plan",
            );
          }}
        />
      </div>

      {tab === "plan" ? (
        <>
          <div className="relative flex h-[44px] items-center px-[12px]">
            <Segmented
              size="small"
              label={COPY.procedures}
              active={grouping === "class" ? COPY.byClass : COPY.byProcedure}
              options={[COPY.byClass, COPY.byProcedure]}
              onChange={(label) => {
                setGrouping(label === COPY.byClass ? "class" : "procedure");
              }}
            />
            <div className="absolute left-1/2 flex -translate-x-1/2 items-baseline gap-[8px]">
              <span data-plan-title="" className="text-[14.5px] font-medium">
                {title}
              </span>
              <span className="text-[12.5px] text-ink-3">{meta}</span>
            </div>
            <div className="ml-auto flex items-center gap-[8px]">
              {data.template_name != null && (
                <Tag data-plan-template="">
                  {fill(COPY.template, { name: data.template_name })}
                </Tag>
              )}
              <Button
                variant="secondary"
                size="sm"
                disabled={draft || !can(data, "close_plan.edit")}
                loading={createDraft.isPending}
                onClick={() => {
                  createDraft.mutate({ path, body: {} });
                }}
              >
                {COPY.editPlan}
              </Button>
              {mayRequest ? (
                <Button
                  variant="primary"
                  size="sm"
                  disabled={data.publish_requested === true}
                  onClick={() => {
                    requestPublish.mutate({
                      path: { client_id: clientId, version: data.version },
                    });
                  }}
                >
                  {COPY.requestPublish}
                </Button>
              ) : (
                <Button
                  variant="primary"
                  size="sm"
                  opensDialog={false}
                  disabled={!mayPublish || unadopted > 0 || (changes === 0 && !agentDraft)}
                  onClick={() => {
                    setPublishOpen(true);
                  }}
                >
                  {fill(COPY.publish, { version: nextVersion })}
                </Button>
              )}
            </div>
          </div>
          <TallyStrip
            className="px-[12px]"
            label={COPY.closePlan}
            items={[
              { label: COPY.tally.accounts, value: String(accountsOf(rows)) },
              { label: COPY.tally.procedures, value: String(data.tally.procedures) },
              {
                label: COPY.tally.requests,
                value: fill(COPY.tally.requestsValue, { n: data.tally.requests_per_month }),
              },
              { label: COPY.tally.manager, value: String(data.tally.manager) },
              { label: COPY.tally.senior, value: String(data.tally.senior) },
              ...(data.aje_policy == null
                ? []
                : [{ label: COPY.tally.ajePolicy, value: data.aje_policy.label }]),
            ]}
          />
          <section className="m-[12px] flex min-h-0 flex-1 flex-col rounded-pane bg-card shadow-e2">
            <header className="relative flex h-[46px] items-center px-[12px]">
              <SearchField
                label={COPY.search}
                placeholder={COPY.search}
                value={q}
                onChange={setQ}
                className="w-[220px]"
              />
              <span className="absolute left-1/2 -translate-x-1/2 text-[14.5px] font-medium">
                {COPY.procedures}
              </span>
              <Button
                variant="secondary"
                size="sm"
                icon="plus"
                className="ml-auto"
                disabled={!draft}
              >
                {COPY.addProcedure}
              </Button>
            </header>
            {initial.drafting !== undefined ? (
              <div
                data-drafting=""
                className="mx-[12px] mb-[8px] rounded-card bg-card p-[10px] shadow-e1"
              >
                <ProgressBar
                  done={initial.drafting.done}
                  total={initial.drafting.total}
                  left={fill(COPY.drafting, {
                    done: initial.drafting.done,
                    total: initial.drafting.total,
                  })}
                  right={fill(COPY.agentDraftMeta, {
                    date: date(initial.drafting.at, { now, withYear: true }),
                    name: initial.drafting.requestedBy,
                  }).replace(/^Drafting · /, "")}
                />
              </div>
            ) : null}
            <div className="min-h-0 flex-1 overflow-auto">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="h-[30px] bg-band-hd text-left text-[11.5px] font-medium text-ink-2">
                    <th className="w-[250px] px-[12px]">{COPY.columns.account}</th>
                    <th className="w-[120px] px-[8px]">{COPY.columns.procedure}</th>
                    <th className="w-[270px] px-[8px]">{COPY.columns.method}</th>
                    <th className="w-[210px] px-[8px]">{COPY.columns.evidence}</th>
                    <th className="w-[120px] px-[8px]">{COPY.columns.source}</th>
                    <th className="w-[140px] px-[8px]">{COPY.columns.review}</th>
                    <th className="w-[80px] px-[8px]">{COPY.columns.frequency}</th>
                    <th className="px-[8px]">{COPY.columns.threshold}</th>
                  </tr>
                </thead>
                <tbody>
                  {groupsOf(shown, grouping).map((g) => (
                    <GroupRows key={g.key} name={g.key}>
                      {g.rows.map((row) => (
                        <PlanRow
                          key={row.row_id}
                          row={row}
                          edit={draft}
                          hovered={hoverId === row.row_id && drawerId === null}
                          onHover={(on) => {
                            setHover(on ? row.row_id : null);
                          }}
                          onOpen={() => {
                            setDrawer(row.row_id);
                          }}
                          onAdopt={() => {
                            adopt.mutate({
                              path: {
                                client_id: clientId,
                                version: data.version,
                                row_id: row.row_id,
                              },
                              headers: { "If-Match": String(data.row_version) },
                            });
                          }}
                        />
                      ))}
                    </GroupRows>
                  ))}
                </tbody>
              </table>
              <p className="px-[12px] py-[10px] text-[11.5px] text-ink-3">{COPY.footnote}</p>
            </div>
          </section>
        </>
      ) : tab === "requests" ? (
        <section data-tab="requests" className="m-[12px] rounded-pane bg-card shadow-e2">
          <header className="flex h-[46px] items-center justify-center text-[14.5px] font-medium">
            {COPY.requests.title}
          </header>
          <ul>
            {data.request_templates.map((t) => (
              <li
                key={t.template_id}
                data-request-template=""
                className="flex h-[40px] items-center justify-between border-t border-hair px-[12px] text-[12.5px]"
              >
                <span>{t.title}</span>
                <span className="text-ink-3">
                  {fill(COPY.requests.due, { n: t.due_business_day })}
                </span>
              </li>
            ))}
          </ul>
        </section>
      ) : (
        <section data-tab="history" className="m-[12px] rounded-pane bg-card shadow-e2">
          <header className="flex h-[46px] items-center justify-center text-[14.5px] font-medium">
            {COPY.history.title}
          </header>
          <ul>
            {(history.data?.items ?? []).map((h) => (
              <li
                key={h.version}
                data-history={h.version}
                className="flex h-[40px] items-center gap-[8px] border-t border-hair px-[12px] text-[12.5px]"
              >
                <span className="font-medium">v{h.version}</span>
                <span className="text-ink-3">·</span>
                <span>{h.attribution}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <Drawer
        open={open !== null}
        onOpenChange={(o) => {
          if (!o) setDrawer(null);
        }}
        title={open?.account_name ?? ""}
        width={480}
      >
        {open !== null ? (
          <Card
            row={open}
            edit={draft}
            onPatch={(c) => {
              patchRow(open, c);
            }}
          />
        ) : null}
      </Drawer>

      <ConfirmDialog
        open={publishOpen && mayPublish}
        onOpenChange={setPublishOpen}
        title={fill(COPY.publishTitle, { version: data.version })}
        confirmLabel={fill(COPY.publish, { version: data.version })}
        destructive={false}
        onConfirm={() => {
          publish.mutate({
            path: { client_id: clientId, version: data.version },
            headers: { "If-Match": String(data.row_version) },
            body: { effective_from: effective },
          });
        }}
      >
        {fill(COPY.publishBody, {
          next: monthYear(effective),
          current: monthYear(previousMonth).split(" ")[0] ?? "",
          previous: data.version - 1,
        })}
      </ConfirmDialog>
    </div>
  );
}

function GroupRows({ name, children }: { name: string; children: JSX.Element[] }): JSX.Element {
  return (
    <>
      <tr data-group={name} className="h-[24px] bg-band-hd">
        <td
          colSpan={8}
          className="px-[12px] text-[10px] font-medium uppercase tracking-[.07em] text-ink-3"
        >
          {name}
        </td>
      </tr>
      {children}
    </>
  );
}

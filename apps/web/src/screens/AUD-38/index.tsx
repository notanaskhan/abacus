// AUD-38 · Hand off audited TB to tax (T-06-T45; TASK-8935; docs/screens/AUD-38.md; handoff AUD-38
// a–e; SPEC-702 F6 AC-27 to AC-31; DEC-5937): the O3 sheet (500) over AUD-06 at
// `?ov=tax-handoff:<auditWorkItemId>`, CLS-12's grammar. Every figure and name is the C12 preview's
// (`…/tax-handoff/targets`, `…/preview`): code's counts, book income, schedules, items. The person
// chooses how each review account travels and what is carried; "Hand off" is the only primary
// button and stays disabled until every review account has a choice (b) and the gate is released
// (d). After the hand-off (c) the toast and the TXP-13 banner preview read the server's landing.
// Nothing here posts to the audited TB or the client's ledger; the agent hands off nothing.
import type {
  TbHandoffLandingOut,
  TbHandoffMappingRowOut,
  TbHandoffPreviewOut,
} from "@abacus/api-client";
import {
  handoffCreateMutation,
  handoffPreviewOptions,
  handoffTargetsOptions,
  returnHandoffOptions,
} from "@abacus/api-client/query";
import {
  Button,
  DASH,
  Icon,
  Pill,
  Segmented,
  SheetModal,
  Skeleton,
  Toggle,
  Tooltip,
  amount,
  date,
  time,
  toast,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, type ReactNode, useState } from "react";
import { useNow } from "../../app-core/clock";
import { useOpenHref } from "../../app-core/open";
import { useAuditCockpit } from "../../domain/audits";
import { handoffLine } from "../../domain/tax";
import { hrefOf, to } from "../../routes/to";
import { COPY as C } from "./copy";

type Travel = "send_blank" | "map_suggested";

function Fieldset({ title, children }: { title: string; children: ReactNode }): JSX.Element {
  return (
    <section aria-label={title} className="overflow-hidden rounded-[10px] bg-card shadow-e1">
      <h3 className="flex h-[33px] items-center bg-band-hd px-[12px] text-[13.5px] font-medium">
        {title}
      </h3>
      {children}
    </section>
  );
}

function Row({
  k,
  children,
  detail,
}: {
  k: string;
  children: ReactNode;
  detail?: string | null;
}): JSX.Element {
  return (
    <div className="flex min-h-[34px] items-start justify-between gap-[12px] px-[12px] py-[7px] hairline-b text-[13px]">
      <span className="flex-none text-ink-2">{k}</span>
      <span className="min-w-0 text-right font-medium">
        {children}
        {detail ? (
          <span className="block text-[11.5px] font-normal text-ink-3">{detail}</span>
        ) : null}
      </span>
    </div>
  );
}

const money = (v: string): string => amount(v, "whole").text;

/** The O4 table of every account and how it travels. */
function Mappings({
  rows,
  open,
  onClose,
}: {
  rows: readonly TbHandoffMappingRowOut[];
  open: boolean;
  onClose: () => void;
}): JSX.Element {
  return (
    <SheetModal
      open={open}
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
      title={C.table.title}
    >
      <table data-aud38="mappings" className="w-full border-collapse text-[12.5px]">
        <thead>
          <tr className="hairline-b text-ink-2">
            {[C.table.account, C.table.balance, C.table.taxCode, C.table.source].map((h) => (
              <th key={h} scope="col" className="h-[30px] px-[8px] text-left font-normal">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.account_ref} className="h-[30px] hairline-b" data-account={r.account_ref}>
              <td className="px-[8px]">{`${r.account_ref} ${r.account_name}`}</td>
              <td className="px-[8px] text-right tabular-nums">{money(r.balance)}</td>
              <td className="px-[8px]">{r.tax_line ?? DASH}</td>
              <td className="px-[8px] text-ink-2">{C.table.sources[r.source] ?? r.source}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </SheetModal>
  );
}

function StackedBar({ p }: { p: TbHandoffPreviewOut }): JSX.Element {
  const { mapped, suggested, review, total } = p.counts;
  const pct = (n: number): string => `${String(total === 0 ? 0 : (n * 100) / total)}%`;
  return (
    <div aria-hidden className="mx-[12px] mt-[10px] flex h-[6px] overflow-hidden rounded-pill">
      <span className="bg-p2" style={{ width: pct(mapped) }} />
      <span className="bg-p3" style={{ width: pct(suggested) }} />
      <span className="bg-p4" style={{ width: pct(review) }} />
    </div>
  );
}

export interface AUD38Props {
  /** The audit work item the sheet opens over (AUD-06's cockpit). */
  workItemId: string;
  close: () => void;
}

export function AUD38({ workItemId, close }: AUD38Props): JSX.Element {
  const now = useNow();
  const openHref = useOpenHref();
  const queries = useQueryClient();
  const cockpit = useAuditCockpit(workItemId);
  const engagementId = cockpit.data?.engagement_id ?? "";
  const targets = useQuery({
    ...handoffTargetsOptions({ path: { engagement_id: engagementId } }),
    enabled: engagementId !== "",
    retry: false,
  });
  const target = targets.data?.items[0];
  const targetId = target?.target_work_item_id ?? "";
  const preview = useQuery({
    ...handoffPreviewOptions({
      path: { engagement_id: engagementId },
      query: { target_work_item_id: targetId },
    }),
    enabled: targetId !== "",
    retry: false,
  });
  const landing = useQuery({
    ...returnHandoffOptions({ path: { return_id: targetId } }),
    enabled: targetId !== "",
    retry: false,
  });
  const [choices, setChoices] = useState<Record<string, Travel>>({});
  const [schedulesOff, setSchedulesOff] = useState<ReadonlySet<string>>(new Set());
  const [items, setItems] = useState<Record<string, boolean>>({});
  const [allOpen, setAllOpen] = useState(false);
  const [done, setDone] = useState(false);
  const create = useMutation({
    ...handoffCreateMutation(),
    onSuccess: async (out) => {
      setDone(true);
      toast.show(
        C.toast(
          preview.data?.target?.return_label.split(" · ")[0] ?? target?.return_label ?? "",
          out.tax_issues_created,
          out.accounts_to_map,
        ),
      );
      await queries.invalidateQueries();
    },
  });
  const p = preview.data;
  const taxItems = p?.tax_items ?? [];
  const body = ((): ReactNode => {
    if (
      preview.isError ||
      targets.isError ||
      (targets.data !== undefined && target === undefined)
    ) {
      return <p className="p-[12px] text-[13px] text-ink-2">{C.unavailable}</p>;
    }
    if (p === undefined) return <Skeleton aria-busy="true" className="h-[600px] w-full" />;
    return null;
  })();
  const choiceOf = (ref: string, server: string | null | undefined): Travel | undefined =>
    choices[ref] ?? (server === "send_blank" || server === "map_suggested" ? server : undefined);
  const unchosen =
    p?.review_accounts.filter((a) => choiceOf(a.account_ref, a.choice) === undefined).length ?? 0;
  const released = p !== undefined && p.gate !== "not_released";
  const canHandOff = p !== undefined && released && unchosen === 0 && !done && !create.isPending;
  const team = p?.target?.team ?? [];
  const preparer = team[0]?.replace(/ \(.*\)$/u, "") ?? "";
  const land: TbHandoffLandingOut | undefined = landing.data;
  const handOff = (): void => {
    if (p === undefined || !canHandOff) return;
    create.mutate({
      path: { engagement_id: engagementId },
      body: {
        target_work_item_id: targetId,
        seen_preview_hash: p.preview_hash,
        account_choices: p.review_accounts.map((a) => ({
          account_ref: a.account_ref,
          choice: choiceOf(a.account_ref, a.choice) ?? "send_blank",
        })),
        schedules: (p.schedule_rows ?? [])
          .filter((s) => !schedulesOff.has(s.key))
          .map((s) => s.key),
        tax_items: taxItems.filter((i) => items[i.key] ?? i.included).map((i) => i.key),
      },
      headers: { "Idempotency-Key": `aud38-${engagementId}-${p.preview_hash}` },
    });
  };
  const action = (
    <Tooltip
      content={!released ? C.notAvailable : unchosen > 0 ? C.needsReviewTip(unchosen) : C.handOff}
    >
      <span>
        <Button variant="primary" size="sm" disabled={!canHandOff} onClick={handOff}>
          {C.handOff}
        </Button>
      </span>
    </Tooltip>
  );
  return (
    <SheetModal
      open
      onOpenChange={(o) => {
        if (!o) close();
      }}
      title={C.title}
      action={action}
    >
      <div data-screen="AUD-38" className="flex flex-col gap-[12px]">
        {body ??
          (p === undefined ? null : (
            <>
              {!released ? (
                <p
                  role="status"
                  className="rounded-[8px] bg-amber-tint px-[12px] py-[8px] text-[12.5px] text-amber-ink"
                >
                  {C.notAvailable}
                </p>
              ) : p.gate === "superseded" ? (
                <p
                  role="status"
                  data-aud38="superseded"
                  className="rounded-[8px] bg-amber-tint px-[12px] py-[8px] text-[12.5px] text-amber-ink"
                >
                  {C.superseded(
                    land?.handed_off_at == null ? DASH : date(land.handed_off_at, { now }),
                    team
                      .map((t) => t.replace(/ \(.*\)$/u, ""))
                      .join(", ")
                      .replace(/, ([^,]*)$/u, " and $1"),
                  )}
                </p>
              ) : unchosen > 0 && !done ? (
                <p
                  role="status"
                  data-aud38="needs-review"
                  className="flex h-[32px] items-center rounded-[8px] bg-amber-tint px-[12px] text-[12.5px] text-amber-ink"
                >
                  {C.needsReview(unchosen)}
                </p>
              ) : null}
              {done && land?.handoff_id != null ? (
                <div
                  data-aud38="landed"
                  className="overflow-hidden rounded-[10px] bg-card shadow-e1"
                >
                  <div className="flex min-h-[36px] items-center gap-[8px] bg-nested px-[12px] text-[12.5px] text-ink-2">
                    <Icon name="link-2" size={13} />
                    <span className="flex-1">
                      {handoffLine(land, now)}
                      <span className="block text-[11.5px] text-ink-3">
                        {C.by(
                          land.handed_off_by ?? DASH,
                          land.handed_off_at == null ? DASH : time(land.handed_off_at),
                        )}
                      </span>
                    </span>
                  </div>
                  {land.book_income ? (
                    <p className="px-[12px] py-[8px] text-[12.5px]">
                      {C.m1Strip(
                        money(land.book_income.net_income),
                        land.candidates?.[0] ? money(land.candidates[0].amount) : null,
                      )}
                    </p>
                  ) : null}
                  <div className="px-[12px] pb-[10px]">
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => {
                        openHref(hrefOf(to.TXP13({ returnId: targetId })));
                      }}
                    >
                      {C.openTxp13}
                    </Button>
                  </div>
                </div>
              ) : null}
              <Fieldset title={C.source.title}>
                <Row k={C.source.engagement}>{p.source?.engagement_label ?? DASH}</Row>
                <Row k={C.source.tb}>{p.source?.tb_label ?? DASH}</Row>
                <Row k={C.source.released}>
                  {p.source?.released_on == null
                    ? DASH
                    : `${date(p.source.released_on, { now, withYear: true })}${p.source.released_by ? ` · ${p.source.released_by}` : ""}`}
                </Row>
                <Row k={C.source.snapshot}>{C.source.snapshotValue}</Row>
                <Row k={C.source.balanced}>
                  {p.source?.balanced === true ? (
                    <Pill variant="green-tint" size="sm">
                      {C.source.balancedPill}
                    </Pill>
                  ) : (
                    DASH
                  )}
                </Row>
                <Row k={C.source.book}>
                  {C.source.bookValue(
                    money(p.book_income.pretax),
                    money(p.book_income.income_tax_expense),
                    money(p.book_income.net_income),
                  )}
                </Row>
              </Fieldset>
              <Fieldset title={C.target.title}>
                <Row k={C.target.return} detail={p.target?.return_detail ?? null}>
                  {p.target?.return_label ?? target?.return_label ?? DASH}
                </Row>
                {p.target?.engagement_created_on != null ? (
                  <Row k={C.target.engagement}>
                    {C.target.engagementValue(
                      date(p.target.engagement_created_on, { now }),
                      p.target.extension_filed_on == null
                        ? null
                        : date(p.target.extension_filed_on, { now }),
                      p.target.due_on == null
                        ? null
                        : date(p.target.due_on, { now, withYear: true }),
                    )}
                  </Row>
                ) : null}
                <Row k={C.target.team}>{team.length > 0 ? team.join(" · ") : DASH}</Row>
                <Row k={C.target.landsAs}>{C.target.landsAsValue}</Row>
              </Fieldset>
              <Fieldset title={C.mapping.title(p.counts.total)}>
                <StackedBar p={p} />
                <ul className="px-[12px] py-[6px] text-[12.5px]" data-aud38="legend">
                  <li className="flex h-[28px] items-center gap-[6px]">
                    <Icon name="check" size={12} />
                    {C.mapping.priorYear(p.counts.mapped)}
                  </li>
                  <li className="flex min-h-[28px] items-center gap-[6px]">
                    <Icon name="atom" size={12} />
                    {C.mapping.suggested(p.counts.suggested)}
                  </li>
                  <li className="flex h-[28px] items-center gap-[6px]">
                    <Icon name="triangle-alert" size={12} />
                    {C.mapping.review(p.counts.review)}
                  </li>
                </ul>
                {p.review_accounts.map((a) => {
                  const chosen = choiceOf(a.account_ref, a.choice);
                  return (
                    <div
                      key={a.account_ref}
                      data-review={a.account_ref}
                      data-chosen={chosen ?? "none"}
                      className={`mx-[12px] mb-[8px] flex items-start gap-[10px] rounded-[8px] p-[10px] text-[12.5px] ${chosen === undefined ? "bg-amber-tint" : "bg-nested"}`}
                    >
                      <span className="min-w-0 flex-1">
                        <span className="block">{`${a.account_ref} ${a.account_name} · ${money(a.balance)}`}</span>
                        {a.detail ? (
                          <span className="block text-[11.5px] text-ink-3">{a.detail}</span>
                        ) : null}
                      </span>
                      <Segmented
                        size="small"
                        label={C.mapping.travelLabel(a.account_ref)}
                        options={[C.mapping.sendBlank, C.mapping.useSuggestion]}
                        active={
                          chosen === undefined
                            ? null
                            : chosen === "send_blank"
                              ? C.mapping.sendBlank
                              : C.mapping.useSuggestion
                        }
                        onChange={(label) => {
                          setChoices((was) => ({
                            ...was,
                            [a.account_ref]:
                              label === C.mapping.sendBlank ? "send_blank" : "map_suggested",
                          }));
                        }}
                      />
                    </div>
                  );
                })}
                <p className="px-[12px] text-[11.5px] text-ink-3">
                  {C.mapping.blankNote(preparer)}
                </p>
                <div className="px-[12px] pb-[10px]">
                  <button
                    type="button"
                    className="text-[12.5px] text-ink hover:underline"
                    onClick={() => {
                      setAllOpen(true);
                    }}
                  >
                    {C.mapping.viewAll(p.counts.total)}
                  </button>
                </div>
              </Fieldset>
              {(p.schedule_rows ?? []).length > 0 ? (
                <Fieldset title={C.schedules.title}>
                  {(p.schedule_rows ?? []).map((s) => (
                    <div
                      key={s.key}
                      data-schedule={s.key}
                      className="flex items-start gap-[10px] px-[12px] py-[8px] hairline-b"
                    >
                      <span className="min-w-0 flex-1 text-[13px]">
                        {s.label}
                        <span className="block text-[11.5px] text-ink-3">{s.detail}</span>
                      </span>
                      <Toggle
                        label={s.label}
                        checked={!schedulesOff.has(s.key)}
                        onChange={(on) => {
                          setSchedulesOff((was) => {
                            const next = new Set(was);
                            if (on) next.delete(s.key);
                            else next.add(s.key);
                            return next;
                          });
                        }}
                      />
                    </div>
                  ))}
                </Fieldset>
              ) : null}
              {taxItems.length > 0 ? (
                <Fieldset title={C.items.title}>
                  {taxItems.map((i) => (
                    <div
                      key={i.key}
                      data-item={i.key}
                      className="flex items-start gap-[10px] px-[12px] py-[8px] hairline-b text-[12.5px]"
                    >
                      <Icon name="triangle-alert" size={15} />
                      <span className="min-w-0 flex-1">
                        <span className="font-medium">{`${i.label} ${money(i.amount)}`}</span>
                        {i.detail ? <> — {i.detail}</> : null}
                      </span>
                      {i.issue_offered !== false ? (
                        <Toggle
                          label={`${C.items.createIssue}: ${i.label}`}
                          checked={items[i.key] ?? i.included}
                          onChange={(on) => {
                            setItems((was) => ({ ...was, [i.key]: on }));
                          }}
                        />
                      ) : null}
                    </div>
                  ))}
                </Fieldset>
              ) : null}
              {p.independence ? (
                <Fieldset title={C.independence}>
                  <p className="px-[12px] py-[8px] text-[12.5px] leading-[1.5] text-ink-2">
                    {p.independence}
                  </p>
                </Fieldset>
              ) : null}
              <p className="text-[11.5px] leading-[1.45] text-ink-3">{C.note}</p>
              <Mappings
                rows={p.accounts ?? []}
                open={allOpen}
                onClose={() => {
                  setAllOpen(false);
                }}
              />
            </>
          ))}
      </div>
    </SheetModal>
  );
}

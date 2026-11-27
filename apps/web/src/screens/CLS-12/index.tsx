// CLS-12 · Tax hand-off (C-02-T48; TASK-9026; DEC-6031): the O3 sheet over CLS-02 for a locked
// December close (C-02-T39's read and publish). The browser draws what the read says: the source
// close and its TB tie, the target return and its tax team, the schedules code computed with a
// toggle each, and the close's tax-relevant items with "Create tax issue". "Hand off" is a
// person's act with the version they saw; after it the toast names the return and the issues, and
// the sheet previews TXP-02's provenance banner (c, c2). A reopened close shows the supersede
// banner (d). Focus stays in the sheet until Escape or ✕ returns it (O3's trap).
import type { DeliveryHandoffOut } from "@abacus/api-client";
import {
  closeTaxHandoffOptions,
  closeTaxHandoffPublishMutation,
  closeTaxHandoffQueryKey,
} from "@abacus/api-client/query";
import {
  Button,
  Fieldset,
  Icon,
  Pill,
  SheetModal,
  Skeleton,
  Toggle,
  amount,
  date,
  time,
  toast,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, type ReactNode, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { useNow } from "../../app-core/clock";
import { hrefOf, to } from "../../routes/to";
import { COPY as C } from "./copy";

export interface CLS12Props {
  closeId: string;
  /** The client's name for the Target row (the close's own read names it). */
  client: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onViewClose?: () => void;
}

function Row({ k, children }: { k: string; children: ReactNode }): JSX.Element {
  return (
    <div className="flex min-h-[34px] items-center justify-between gap-[12px] px-[14px] hairline-b last:shadow-none">
      <dt className="text-[13px] text-ink-2">{k}</dt>
      <dd className="text-right text-[13px] font-medium">{children}</dd>
    </div>
  );
}

function figuresOf(raw: Record<string, string> | undefined, year: number): Record<string, string> {
  const out: Record<string, string> = { year: String(year) };
  for (const [k, v] of Object.entries(raw ?? {})) out[k] = amount(v, "cents").text;
  return out;
}

function idempotency(): { "Idempotency-Key": string } {
  return { "Idempotency-Key": `cls12-${crypto.randomUUID()}` };
}

function Body({
  closeId,
  data,
  client,
  carry,
  setCarry,
  issues,
  setIssues,
  onViewClose,
}: {
  closeId: string;
  data: DeliveryHandoffOut;
  client: string;
  carry: Record<string, boolean>;
  setCarry: (key: string, on: boolean) => void;
  issues: Record<string, boolean>;
  setIssues: (id: string, on: boolean) => void;
  onViewClose: (() => void) | undefined;
}): JSX.Element {
  const now = useNow();
  const navigate = useNavigate();
  const year = data.target_tax_year ?? 2026;
  const locked = data.locked_at ? date(data.locked_at, { now, withYear: true }) : "—";
  const handedOff = data.status === "handed_off";
  return (
    <div className="flex flex-col gap-[12px] p-[12px]" data-cls12="body">
      {data.superseded_on_next && data.reopened_at ? (
        <p
          role="status"
          data-cls12="superseded"
          className="rounded-nested bg-amber-tint px-[12px] py-[9px] text-[12.5px] text-amber-ink"
        >
          {C.superseded(
            date(data.reopened_at, { now }),
            data.target_preparer ?? null,
            data.target_reviewer ?? null,
          )}
        </p>
      ) : null}
      {handedOff && data.handed_off_at ? (
        <section aria-label={C.preview} data-cls12="provenance">
          <p className="flex h-[36px] items-center justify-between rounded-nested bg-nested px-[12px] text-[12.5px] text-ink-2">
            <span>
              {C.banner(
                locked,
                data.handed_off_by ?? "—",
                `${date(data.handed_off_at, { now, withYear: true })}, ${time(data.handed_off_at)}`,
              )}
            </span>
            <button
              type="button"
              className="font-medium text-ink"
              onClick={() => {
                if (onViewClose !== undefined) onViewClose();
                else void navigate(to.CLS02({ closeId }));
              }}
            >
              {C.viewClose}
            </button>
          </p>
          {data.target_return_id ? (
            <button
              type="button"
              className="mt-[6px] text-[12.5px] font-medium"
              onClick={() => {
                if (data.target_return_id) {
                  void navigate(to.TXP10({ returnId: data.target_return_id }));
                }
              }}
            >
              {C.openIssues}
            </button>
          ) : null}
        </section>
      ) : null}
      <Fieldset title={C.source}>
        <dl>
          <Row k={C.keys.close}>{C.closeValue(`December ${String(year)}`, locked)}</Row>
          <Row k={C.keys.tb}>{C.tbValue(data.tb_version ?? "—", year)}</Row>
          <Row k={C.keys.balanced}>
            {data.balanced === true ? (
              <span className="inline-flex items-center gap-[6px]">
                <Pill variant="green">{C.tie}</Pill>
                <span className="font-normal text-ink-3">{C.balancedValue}</span>
              </span>
            ) : (
              "—"
            )}
          </Row>
          <Row k={C.keys.entries}>{C.entriesValue}</Row>
        </dl>
      </Fieldset>
      <Fieldset title={C.target}>
        <dl>
          <Row k={C.keys.ret}>
            {data.target_form ? C.returnValue(data.target_form, year, client) : "—"}
          </Row>
          <Row k={C.keys.engine}>{data.target_engine ?? "—"}</Row>
          <Row k={C.keys.team}>
            {C.teamValue(data.target_preparer ?? null, data.target_reviewer ?? null) || "—"}
          </Row>
          <Row k={C.keys.landsAs}>{C.landsAsValue}</Row>
        </dl>
      </Fieldset>
      <Fieldset title={C.carried}>
        <ul>
          {(data.schedules ?? []).map((s) => (
            <li
              key={s.key}
              data-schedule={s.key}
              className="flex items-start justify-between gap-[12px] px-[14px] py-[8px] hairline-b"
            >
              <span className="flex flex-col">
                {/* The schedule's workpaper opens in a new tab (CLS-04). */}
                <a
                  href={hrefOf(to.CLS04({ closeId }))}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[13px] text-ink"
                >
                  {s.label}
                </a>
                <span className="text-[12.5px] text-ink-3">
                  {(C.schedule[s.key] ?? (() => ""))(figuresOf(s.figures, year))}
                </span>
              </span>
              <Toggle
                label={s.label}
                checked={carry[s.key] ?? s.included}
                disabled={handedOff}
                onChange={(on) => {
                  setCarry(s.key, on);
                }}
              />
            </li>
          ))}
        </ul>
      </Fieldset>
      <Fieldset title={C.items}>
        <ul>
          {(data.items ?? []).map((i) => (
            <li
              key={i.issue_id}
              data-item={i.issue_id}
              className="flex items-start justify-between gap-[12px] px-[14px] py-[8px] hairline-b"
            >
              <Icon name="triangle-alert" size={15} className="mt-[1px] flex-none text-amber" />
              <button
                type="button"
                className="flex-1 text-left text-[12.5px]"
                onClick={() => {
                  void navigate(to.CLS06({ closeId }));
                }}
              >
                {i.title}
              </button>
              <Toggle
                label={`${C.createIssue}: ${i.title}`}
                checked={issues[i.issue_id] ?? i.create_tax_issue ?? true}
                disabled={handedOff}
                onChange={(on) => {
                  setIssues(i.issue_id, on);
                }}
              />
            </li>
          ))}
        </ul>
      </Fieldset>
      <p className="text-[11.5px] leading-[1.45] text-ink-3">{C.note}</p>
    </div>
  );
}

export function CLS12({
  closeId,
  client,
  open,
  onOpenChange,
  onViewClose,
}: CLS12Props): JSX.Element {
  const queries = useQueryClient();
  const path = { close_id: closeId };
  const q = useQuery({ ...closeTaxHandoffOptions({ path }), enabled: open });
  const [carry, setCarryState] = useState<Record<string, boolean>>({});
  const [issues, setIssueState] = useState<Record<string, boolean>>({});
  const publish = useMutation({
    ...closeTaxHandoffPublishMutation(),
    onSuccess: async (out) => {
      const d = q.data;
      toast.show({
        kind: "info",
        text: C.handedOff(
          d?.target_form ?? "",
          d?.target_tax_year ?? 2026,
          out.tax_issues_created,
        ),
      });
      await queries.invalidateQueries({ queryKey: closeTaxHandoffQueryKey({ path }) });
    },
    onError: () => {
      toast.show({ kind: "error", text: C.failedToLoad });
    },
  });
  const data = q.data;
  const ready = data?.status === "ready";
  const handOff = (): void => {
    if (data === undefined) return;
    publish.mutate({
      path,
      body: {
        seen_version: data.version ?? 1,
        schedules: (data.schedules ?? [])
          .filter((s) => carry[s.key] ?? s.included)
          .map((s) => s.key),
        items: (data.items ?? [])
          .filter((i) => issues[i.issue_id] ?? i.create_tax_issue ?? true)
          .map((i) => i.issue_id),
      },
      headers: idempotency(),
    });
  };
  return (
    <SheetModal
      open={open}
      onOpenChange={onOpenChange}
      title={C.title}
      action={
        <Button
          variant="primary"
          size="sm"
          disabled={!ready || publish.isPending}
          onClick={handOff}
          data-cls12="hand-off"
        >
          {C.handOff}
        </Button>
      }
    >
      {q.isPending ? (
        <Skeleton className="m-[12px] h-[400px]" />
      ) : data === undefined ? (
        <div role="alert" className="flex flex-col items-start gap-[8px] p-[24px]">
          <p className="text-[13px]">{C.failedToLoad}</p>
          <Button variant="secondary" size="sm" onClick={() => void q.refetch()}>
            {C.retry}
          </Button>
        </div>
      ) : data.status === "not_available" ? (
        <p role="status" className="p-[24px] text-[13px] text-ink-2" data-cls12="not-available">
          {data.reason ?? C.notAvailable}
        </p>
      ) : (
        <Body
          closeId={closeId}
          data={data}
          client={client}
          carry={carry}
          setCarry={(key, on) => {
            setCarryState((cur) => ({ ...cur, [key]: on }));
          }}
          issues={issues}
          setIssues={(id, on) => {
            setIssueState((cur) => ({ ...cur, [id]: on }));
          }}
          onViewClose={onViewClose}
        />
      )}
    </SheetModal>
  );
}

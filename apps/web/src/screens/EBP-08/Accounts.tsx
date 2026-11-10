import type {
  AccountGroupOut,
  AccountRollforwardOut,
  AccountTieOut,
  SdbaOut,
  VestingOut,
} from "@abacus/api-client";
import {
  ebpParticipantAccountsOptions,
  ebpSdbaOptions,
  ebpVestingOptions,
} from "@abacus/api-client/query";
import { type CockpitCanvas, PaneAction, Pill, Segmented, Skeleton, amount, cn } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { useFlag } from "../../app-core/flags";
import { COPY } from "./copy";

// EBP-08 · Participant accounts summary (A-05-T52; A-05 F7; the handoff spec): the Testing ›
// Participant Accounts canvas, T6's statement grammar inside the T2 cockpit. Every figure is the
// server's (A-05-T46): rows crossfoot and the Total foots by code; a tie the server can't read yet
// shows no pill, never a made-up "Ties". No "$" in the statement; negatives in brackets.

export const PARTICIPANT_ACCOUNTS = "ebp_08";
const FLAG = "ebp.modules";
type Tab = keyof typeof COPY.tabs;
const TABS: readonly Tab[] = ["rollforward", "brokerwindow", "vesting"];
const CARD =
  "flex min-w-0 flex-1 flex-col justify-center gap-[4px] rounded-[10px] bg-card e1 px-[12px] py-[6px]";
const LABEL = "text-[9.5px] uppercase tracking-[.07em] text-ink-3";
const TH = "h-[30px] bg-band-hd px-[10px] text-right text-[11.5px] font-medium text-ink-3";
const TD = "h-[30px] px-[10px] text-right text-[12px] tabular-nums";
const GROUP = "h-[30px] px-[10px] text-left text-[10px] uppercase tracking-[.07em] text-ink-3";

const figure = (v: string | null | undefined): string =>
  v === null || v === undefined ? "" : amount(v, "whole").text;
const negative = (v: string): boolean => amount(v, "whole").tone === "neg";

export interface AccountsOptions {
  active?: boolean;
  tab?: Tab;
  onTab?: (tab: Tab) => void;
  /** a: the agent is running (Begin… pressed); the table shows skeleton rows. */
  running?: boolean;
  signedInitials?: string | null;
  onSignOff?: () => void;
  onSourceDocs?: () => void;
  /** A group's figures open its participant accounts (O2 drawer). */
  onGroup?: (status: string) => void;
}

function TiePill({ tie }: { tie: boolean | null | undefined }): JSX.Element | null {
  if (tie !== true) return null;
  return (
    <Pill size="micro" variant="green" check>
      {COPY.tally.ties}
    </Pill>
  );
}

function Tally({
  view,
  running,
}: {
  view: AccountRollforwardOut | undefined;
  running: boolean;
}): JSX.Element {
  const tie = (key: string): boolean | null => view?.ties.find((t) => t.key === key)?.ties ?? null;
  const cell = (key: string, label: string, body: JSX.Element): JSX.Element => (
    <div key={key} className={CARD} data-tally={key}>
      <span className={LABEL}>{label}</span>
      {running ? <span className="text-[12px] text-ink-3">{COPY.tally.pending}</span> : body}
    </div>
  );
  const crossfoots = view !== undefined && view.groups.every((g) => g.crossfoots);
  return (
    <div data-ebp08="tally" className="flex h-[64px] items-center gap-[8px] px-[12px]">
      {cell("trust", COPY.tally.trust, <TiePill tie={tie("net_trust_assets")} />)}
      {cell("earnings", COPY.tally.earnings, <TiePill tie={crossfoots ? true : null} />)}
      {cell(
        "contributions",
        COPY.tally.contributions,
        <TiePill tie={tie("contributions_allocated")} />,
      )}
      {cell(
        "participants",
        COPY.tally.participants,
        <span className="text-[16px] tabular-nums">{view?.total.participants ?? ""}</span>,
      )}
      {cell(
        "forfeiture",
        COPY.tally.forfeiture,
        <span className="text-[16px] tabular-nums">
          {view === undefined
            ? ""
            : amount(view.forfeiture_account, "cents", { zero: "explicit" }).text}
        </span>,
      )}
    </div>
  );
}

function Row({
  label,
  group,
  total,
  onGroup,
}: {
  label: string;
  group: AccountGroupOut;
  total?: boolean;
  onGroup?: (status: string) => void;
}): JSX.Element {
  const values = [
    group.beginning,
    group.contributions,
    group.earnings,
    group.distributions,
    group.fees,
    group.transfers,
    group.ending,
  ];
  return (
    <tr data-group={total ? "total" : group.status} className={cn(total && "font-medium")}>
      <td className={cn(TD, "text-left")}>{label}</td>
      <td className={TD}>{group.participants}</td>
      {values.map((v, i) => (
        <td
          key={i}
          className={cn(TD, negative(v) && "text-red", !total && onGroup && "cursor-pointer")}
          onClick={
            total || onGroup === undefined
              ? undefined
              : () => {
                  onGroup(group.status);
                }
          }
        >
          {total && i === 5 ? "0" : figure(v)}
        </td>
      ))}
    </tr>
  );
}

function TieRow({
  label,
  tie,
  value,
}: {
  label: string;
  tie?: AccountTieOut;
  value: string;
}): JSX.Element {
  return (
    <tr data-tie={tie?.key ?? "line"}>
      <td className={cn(TD, "text-left")} colSpan={7}>
        {label}
      </td>
      <td className={TD}>
        <TiePill tie={tie?.ties} />
      </td>
      <td className={TD}>{figure(value)}</td>
    </tr>
  );
}

function Statement({
  view,
  running,
  onGroup,
}: {
  view: AccountRollforwardOut | undefined;
  running: boolean;
  onGroup?: (status: string) => void;
}): JSX.Element {
  const ties = new Map((view?.ties ?? []).map((t) => [t.key, t]));
  const trust = ties.get("net_trust_assets");
  return (
    <div className="mx-[12px] overflow-hidden rounded-pane bg-card e2" data-ebp08="statement">
      <table className="w-full border-collapse">
        <thead>
          <tr>
            {COPY.columns.map((c, i) => (
              <th key={c} className={cn(TH, i === 0 && "text-left")}>
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {running || view === undefined ? (
            [0, 1, 2].map((i) => (
              <tr key={i} data-skeleton>
                <td colSpan={9} className="px-[10px] py-[10px]">
                  <Skeleton className="h-[9px] w-full" />
                </td>
              </tr>
            ))
          ) : (
            <>
              {view.groups.map((g) => (
                <Row
                  key={g.status}
                  label={COPY.groups[g.status] ?? g.status}
                  group={g}
                  {...(onGroup === undefined ? {} : { onGroup })}
                />
              ))}
              <Row label={COPY.total} group={view.total} total />
              <tr>
                <td colSpan={9} className={GROUP}>
                  {COPY.tieOut}
                </td>
              </tr>
              <TieRow label={COPY.keystone} value={view.total.ending} />
              {trust !== undefined && (
                <TieRow
                  label={COPY.ties.net_trust_assets ?? ""}
                  tie={trust}
                  value={trust.actual}
                />
              )}
              <tr>
                <td colSpan={9} className={GROUP}>
                  {COPY.allocation}
                </td>
              </tr>
              {["contributions_allocated", "distributions", "fees"].map((key) => {
                const tie = ties.get(key);
                return tie === undefined ? null : (
                  <TieRow key={key} label={COPY.ties[key] ?? key} tie={tie} value={tie.actual} />
                );
              })}
            </>
          )}
        </tbody>
      </table>
      <div className="flex gap-[8px] p-[12px]">
        <PaneAction label={COPY.citations} />
        <PaneAction label={COPY.procedures} />
      </div>
    </div>
  );
}

function Brokerage({ sdba }: { sdba: SdbaOut | undefined }): JSX.Element {
  return (
    <div className="mx-[12px] rounded-pane bg-card e2" data-ebp08="brokerage">
      <div className="px-[12px] py-[10px] text-[13px] font-medium">{COPY.brokerage}</div>
      <table className="w-full border-collapse">
        <tbody>
          {(sdba?.rows ?? []).map((r) => (
            <tr key={r.security_type} data-security={r.security_type}>
              <td className={cn(TD, "text-left")}>{r.security_type}</td>
              <td className={TD}>{figure(r.market_value)}</td>
            </tr>
          ))}
          {sdba !== undefined && (
            <tr className="font-medium" data-security="total">
              <td className={cn(TD, "text-left")}>{COPY.brokerageTotal}</td>
              <td className={TD}>
                <span className="mr-[8px]">
                  <TiePill tie={sdba.per_trust === null ? null : sdba.per_trust === sdba.total} />
                </span>
                {figure(sdba.total)}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function Vesting({ vesting }: { vesting: VestingOut | undefined }): JSX.Element {
  const rows = vesting?.rows ?? [];
  return (
    <div className="mx-[12px] rounded-pane bg-card e2" data-ebp08="vesting">
      <div className="flex items-center justify-between px-[12px] py-[10px]">
        <span className="text-[13px] font-medium">{COPY.vestingTitle}</span>
        <span className="text-[11.5px] text-ink-3">{COPY.participants(rows.length)}</span>
      </div>
      <table className="w-full border-collapse">
        <thead>
          <tr>
            {COPY.vestingColumns.map((c, i) => (
              <th key={c} className={cn(TH, i < 2 && "text-left")}>
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.participant_key} data-participant={r.participant_key}>
              <td className={cn(TD, "text-left")}>{r.name}</td>
              <td className={cn(TD, "text-left text-ink-2")}>{r.termination_on}</td>
              <td className={TD}>{r.years_of_service ?? ""}</td>
              <td className={TD}>
                {r.vested_pct === null ? "" : `${String(Number(r.vested_pct))}%`}
              </td>
              <td className={TD}>{r.agrees === true ? COPY.agrees : ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {vesting !== undefined && Number(vesting.forfeitures_arising) === 0 && (
        <p className="px-[12px] py-[10px] text-[12.5px] text-ink-2" data-ebp08="forfeitures">
          {COPY.forfeitures}
        </p>
      )}
    </div>
  );
}

export function useAccountsCanvas(
  workItemId: string,
  options: AccountsOptions = {},
): CockpitCanvas {
  const on = useFlag(FLAG) === true;
  const enabled = options.active !== false && on;
  const path = { work_item_id: workItemId };
  const [localTab, setLocalTab] = useState<Tab>("rollforward");
  const tab = options.tab ?? localTab;
  const running = options.running === true;
  const roll = useQuery({
    ...ebpParticipantAccountsOptions({ path }),
    enabled: enabled && !running,
    retry: false,
  });
  const sdba = useQuery({
    ...ebpSdbaOptions({ path }),
    enabled: enabled && tab === "brokerwindow",
    retry: false,
  });
  const vesting = useQuery({
    ...ebpVestingOptions({ path }),
    enabled: enabled && tab === "vesting",
    retry: false,
  });
  const signed = options.signedInitials != null;
  const source = options.onSourceDocs === undefined ? {} : { onClick: options.onSourceDocs };
  const signOff = options.onSignOff === undefined ? {} : { onClick: options.onSignOff };
  return {
    title: COPY.title,
    actions: (
      <>
        {signed ? (
          <Pill size="chip" variant="green-tint" check>
            {options.signedInitials}
          </Pill>
        ) : (
          <Pill size="micro" variant="neutral">
            {COPY.agentDraft}
          </Pill>
        )}
        <PaneAction label={COPY.edit} />
        <PaneAction label={COPY.signOff} {...signOff} />
        <PaneAction label={COPY.sourceDocs} {...source} />
      </>
    ),
    controls: (
      <div className="flex w-full items-center justify-between">
        <Segmented
          label={COPY.title}
          active={COPY.tabs[tab]}
          onChange={(label) => {
            const next = TABS.find((value) => COPY.tabs[value] === label);
            if (next !== undefined) {
              setLocalTab(next);
              options.onTab?.(next);
            }
          }}
          options={TABS.map((value) => COPY.tabs[value])}
        />
        <PaneAction label={COPY.openInExcel} />
      </div>
    ),
    children: !on ? (
      <p className="m-[12px] text-[12.5px] text-ink-2" data-ebp08="off">
        {COPY.flagOff}
      </p>
    ) : (
      <div
        data-screen="EBP-08"
        data-tab={tab}
        className="relative flex min-h-0 flex-1 flex-col gap-[12px] overflow-y-auto bg-shell pb-[12px]"
      >
        <Tally view={roll.data} running={running} />
        {tab === "rollforward" && (
          <Statement
            view={roll.data}
            running={running}
            {...(options.onGroup === undefined ? {} : { onGroup: options.onGroup })}
          />
        )}
        {tab === "brokerwindow" && <Brokerage sdba={sdba.data} />}
        {tab === "vesting" && <Vesting vesting={vesting.data} />}
        {running && (
          <div
            data-ebp08="running"
            className="absolute bottom-[16px] left-1/2 flex h-[43px] -translate-x-1/2 items-center gap-[8px] rounded-full bg-card px-[16px] text-[12.5px] e2"
          >
            <span
              aria-hidden
              className="h-[12px] w-[12px] animate-spin rounded-full border-[1.5px] border-ink-3 border-t-transparent"
            />
            {COPY.running}
          </div>
        )}
      </div>
    ),
  };
}

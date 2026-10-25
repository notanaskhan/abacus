import type { TbLayerLineOut } from "@abacus/api-client";
import {
  tbCandidatesOptions,
  tbLayerViewOptions,
  tbLeadsheetAreaOptions,
  tieOutChecksOptions,
  trialBalancesOptions,
} from "@abacus/api-client/query";
import { DEFAULT_TZ, amount, dateTime } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import type { JSX } from "react";
import { useNow } from "../../app-core/clock";
import { useSession } from "../../app-core/session";
import { type Aud06State, OPENS } from "./scenarios";

// AUD-06's fixture frames (gallery only; A-02-T05): each scenario's persona, clock and figures read
// through the generated client from its C9 v1 fixtures, so `/components/screens/AUD-06?st=a…h`
// shows what every artboard stands on. Interim: A-02-T09 and A-02-T14 build the screen (T2
// workpaper pane, check strip, evidence-grammar table) on the same scenarios and replace this
// frame. It formats what the server sends and sums nothing.

function money(v: string | null, whole: boolean): string {
  return amount(v, whole ? "whole" : "money").text;
}

function Line({ line, whole, final }: { line: TbLayerLineOut; whole: boolean; final: boolean }) {
  return (
    <tr data-account={line.account_code} className="hairline-b">
      <td className="py-[4px] pr-[12px]">{line.account_name}</td>
      <td className="py-[4px] pr-[12px] text-right tabular-nums">{money(line.boy, whole)}</td>
      <td className="py-[4px] pr-[12px] text-right tabular-nums">{money(line.eoy, whole)}</td>
      {final && (
        <>
          <td data-col="aje" className="py-[4px] pr-[12px] text-right tabular-nums">
            {money(line.aje, whole)}
          </td>
          <td data-col="final" className="py-[4px] pr-[12px] text-right tabular-nums">
            {money(line.final, whole)}
          </td>
        </>
      )}
      <td className="py-[4px] text-meta text-ink-3">
        {[
          ...(line.adjustment_refs ?? []),
          ...(line.flags ?? []).map((f) => f.kind),
          ...(line.ticks ?? []).map((t) =>
            t.actor_kind === "agent" ? "agent tick" : `${t.kind} ${t.initials ?? ""}`.trim(),
          ),
        ].join(" · ")}
      </td>
    </tr>
  );
}

export function AUD06Frame({ state }: { state: Aud06State }): JSX.Element {
  const opens = OPENS[state];
  const session = useSession();
  const now = useNow();
  const tz = session.tz ?? DEFAULT_TZ;
  const engagement = { path: { engagement_id: opens.engagementId } };
  const tbPath =
    opens.tbId === null
      ? null
      : { path: { engagement_id: opens.engagementId, tb_id: opens.tbId } };
  const list = useQuery({ ...trialBalancesOptions(engagement), retry: false });
  const view = useQuery({
    ...tbLayerViewOptions({
      path: {
        engagement_id: opens.engagementId,
        tb_id: opens.tbId ?? "",
        layer: opens.layer,
      },
    }),
    enabled: tbPath !== null && list.isSuccess,
    retry: false,
  });
  const checks = useQuery({
    ...tieOutChecksOptions({ path: tbPath?.path ?? { engagement_id: "", tb_id: "" } }),
    enabled: tbPath !== null && list.isSuccess,
    retry: false,
  });
  const leadsheet = useQuery({
    ...tbLeadsheetAreaOptions({
      path: { ...(tbPath?.path ?? { engagement_id: "", tb_id: "" }), area: opens.area ?? "" },
    }),
    enabled: tbPath !== null && opens.area !== undefined && list.isSuccess,
    retry: false,
  });
  const candidates = useQuery({
    ...tbCandidatesOptions({ path: tbPath?.path ?? { engagement_id: "", tb_id: "" } }),
    enabled: tbPath !== null && list.isSuccess && (view.data?.newer_snapshots ?? 0) > 0,
    retry: false,
  });
  const whole = view.data?.display_unit === "whole_dollars";
  const final = view.data?.layer === "final";
  let body: JSX.Element;
  if (list.isPending) body = <p data-aud06="loading">Loading</p>;
  else if (list.isError) body = <p data-aud06="error">{JSON.stringify(list.error)}</p>;
  else if (list.data.trial_balances.length === 0) {
    body = (
      <ul data-aud06="snapshots">
        {list.data.snapshots.map((s) => (
          <li key={s.id}>
            {`${s.source} · ${String(s.line_count)} lines · ${money(s.total_debit, false)} = ${money(s.total_credit, false)}`}
          </li>
        ))}
      </ul>
    );
  } else if (view.isError) body = <p data-aud06="error">{JSON.stringify(view.error)}</p>;
  else if (view.data === undefined) body = <p data-aud06="loading">Loading</p>;
  else {
    const v = view.data;
    body = (
      <div className="flex flex-col gap-[12px]">
        <p data-aud06="header" className="text-dense text-ink-2">
          {`${v.label} · ${v.layer} · ${v.period_start} – ${v.period_end} · v${String(v.version_no)} · adopted by ${v.provenance.adopted_by_name}`}
        </p>
        {v.newer_snapshots > 0 && (
          <p data-aud06="newer">
            {(candidates.data ?? [])
              .map(
                (s) =>
                  `${String(s.lines_changed ?? 0)} lines changed · net ${money(s.net_change, false)}`,
              )
              .join(" · ")}
          </p>
        )}
        <table data-aud06="lines" className="w-full text-cell">
          <tbody>
            {v.groups
              .flatMap((g) => g.lines)
              .map((l) => (
                <Line key={l.account_code} line={l} whole={whole} final={final} />
              ))}
          </tbody>
        </table>
        <ul data-aud06="totals" className="text-dense">
          {v.totals.map((t) => (
            <li
              key={t.key}
              data-total={t.key}
            >{`${t.label} ${money(t.boy, whole)} ${money(t.eoy, whole)}`}</li>
          ))}
          <li data-total="balance">
            {`Debits ${money(v.balance.debit, whole)} = credits ${money(v.balance.credit, whole)}`}
          </li>
        </ul>
        <ul data-aud06="checks" className="text-dense">
          {(checks.data ?? []).map((c) => (
            <li key={c.id} data-check={c.key} data-status={c.result.status}>
              {`${c.label} · ${c.result.status}${c.result.status === "off" ? ` ${money(c.result.difference, false)}` : ""}${c.result.formula === null ? "" : ` · ${c.result.formula}`}`}
            </li>
          ))}
        </ul>
        {leadsheet.data !== undefined && (
          <table data-aud06="leadsheet" className="w-full text-cell">
            <tbody>
              {leadsheet.data.rows.map((r) => (
                <tr key={r.account_code} data-row={r.account_code}>
                  <td>{r.account_name}</td>
                  <td className="text-right tabular-nums">{amount(r.py, "whole").text}</td>
                  <td className="text-right tabular-nums">{amount(r.cy, "whole").text}</td>
                  <td className="text-right tabular-nums">{amount(r.change, "whole").text}</td>
                  <td className="text-right tabular-nums">
                    {r.change_pct === null ? "" : `${r.change_pct}%`}
                  </td>
                </tr>
              ))}
              <tr data-row="total">
                <td>{leadsheet.data.area}</td>
                <td className="text-right tabular-nums">
                  {amount(leadsheet.data.py, "whole").text}
                </td>
                <td className="text-right tabular-nums">
                  {amount(leadsheet.data.cy, "whole").text}
                </td>
                <td className="text-right tabular-nums">
                  {amount(leadsheet.data.change, "whole").text}
                </td>
                <td className="text-right tabular-nums">
                  {leadsheet.data.change_pct === null ? "" : `${leadsheet.data.change_pct}%`}
                </td>
              </tr>
            </tbody>
          </table>
        )}
      </div>
    );
  }
  return (
    <div
      data-screen="AUD-06"
      data-state={state}
      className="flex flex-col gap-[12px] bg-card p-[16px] text-body"
    >
      <p data-aud06="who" className="text-meta text-ink-3">
        {`${session.user?.displayName ?? ""} · ${dateTime(now, { tz })}${opens.ov === undefined ? "" : ` · ?ov=${opens.ov}`}`}
      </p>
      {body}
    </div>
  );
}

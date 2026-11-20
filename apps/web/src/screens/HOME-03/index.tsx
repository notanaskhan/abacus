// HOME-03 · Deadlines calendar (T-08-T16; docs/screens/HOME-03.md; T-08 §3; SPEC-710 AC-10, AC-11):
// T13. The month grid (five weeks, chips max three then "+n more"), the Week and List views with
// the filters carried over, the person filter, the rule popover (rule, original and extended due,
// extension filed, stage, owner), the day popover, the export menu and the footer note. Every chip
// says its risk in words beside its tint (the server's `risk_label`); chips route to their record
// by source kind. Dates and risk are the server's (ADR-050).
import type {
  FilingDeadlineCalendarOut,
  FilingDeadlineDetailOut,
  FilingDeadlineItemOut,
} from "@abacus/api-client";
import { Button, Pill, type PillVariant, Popover, Segmented, date } from "@abacus/ui";
import { type JSX, useState } from "react";
import { COPY } from "./copy";

export type Home03View = "month" | "week" | "list";
export type ChipTarget = "TAX-02" | "AUD-02" | "CLS-02" | "NOT-02" | "SIG-01" | "TXT-04";

export const TARGET: Record<FilingDeadlineItemOut["source_kind"], ChipTarget> = {
  tax_return: "TAX-02",
  extension: "TAX-02",
  estimate_batch: "TAX-02",
  fiduciary_statement: "TAX-02",
  election_window: "TAX-02",
  notice_response: "NOT-02",
  envelope: "SIG-01",
  close: "CLS-02",
  assurance_report: "AUD-02",
  form_5500: "AUD-02",
  consent: "SIG-01",
};

const TINT: Record<FilingDeadlineItemOut["risk"], PillVariant> = {
  overdue: "red",
  due_7: "red",
  due_30: "amber",
  later: "neutral",
  done: "green",
};

const iso = (d: Date): string => d.toISOString().slice(0, 10);
const short = (s: string): string => date(s, { now: Date.parse(`${s}T12:00:00Z`) });
const long = (s: string): string => date(s, { now: 0, withYear: true });

function Chip({
  item,
  onOpen,
  detail,
  outside = false,
}: {
  item: FilingDeadlineItemOut;
  onOpen?: ((item: FilingDeadlineItemOut) => void) | undefined;
  detail?: FilingDeadlineDetailOut | undefined;
  outside?: boolean;
}): JSX.Element {
  const label = `${item.risk === "done" ? "✓ " : ""}${item.client_name} · ${item.filing_label}`;
  const chip = (
    <button
      type="button"
      data-chip={item.filing_deadline_id}
      data-risk={item.risk}
      aria-label={`${label} · ${item.risk_label}`}
      onClick={() => onOpen?.(item)}
      className={`block max-w-full truncate text-left ${outside ? "opacity-60" : ""}`}
    >
      <Pill variant={TINT[item.risk]}>{label}</Pill>
    </button>
  );
  if (detail === undefined) return chip;
  return (
    <Popover
      trigger={chip}
      open
      width={300}
      label={`${detail.item.client_name} · ${detail.item.filing_label}`}
    >
      <div data-rule-popover="" className="flex flex-col gap-[4px] p-[10px] text-body">
        <h3 className="text-[13.5px] font-medium text-ink">{`${detail.item.client_name} · ${detail.item.filing_label}`}</h3>
        <Kv k={COPY.popover.rule} v={detail.item.rule_text ?? "—"} />
        <Kv k={COPY.popover.original} v={long(detail.original_due_on)} />
        {detail.extended_due_on ? (
          <Kv k={COPY.popover.extended} v={long(detail.extended_due_on)} />
        ) : null}
        {detail.extension_filed_on ? (
          <Kv k={COPY.popover.filed} v={long(detail.extension_filed_on)} />
        ) : null}
        <Kv k={COPY.popover.stage} v={<Pill variant="neutral">{detail.item.stage_label}</Pill>} />
        <Kv
          k={COPY.popover.owner}
          v={`${detail.item.owners.map((o) => o.initials).join(" / ")}${detail.item.signer ? ` · ${COPY.popover.signs(detail.item.signer.initials)}` : ""}`}
        />
        <button
          type="button"
          className="mt-[4px] text-left text-[13px] font-medium text-ink"
          onClick={() => onOpen?.(detail.item)}
        >
          {COPY.popover.open} <span className="text-ink-3">→</span>
        </button>
      </div>
    </Popover>
  );
}

function Kv({ k, v }: { k: string; v: JSX.Element | string }): JSX.Element {
  return (
    <div className="flex h-[30px] items-center justify-between gap-[8px]">
      <span className="text-ink-2">{k}</span>
      <span className="text-right text-ink">{v}</span>
    </div>
  );
}

export interface HOME03Props {
  calendar: FilingDeadlineCalendarOut | undefined;
  view: Home03View;
  onView?: (v: Home03View) => void;
  person?: string | null;
  onOpen?: (item: FilingDeadlineItemOut, target: ChipTarget) => void;
  detail?: FilingDeadlineDetailOut;
  moreOpen?: string;
  onExport?: (format: "ics" | "xlsx") => void;
}

export function HOME03({
  calendar,
  view,
  onView,
  person = null,
  onOpen,
  detail,
  moreOpen,
  onExport,
}: HOME03Props): JSX.Element {
  const [more, setMore] = useState<string | undefined>(moreOpen);
  const open = (i: FilingDeadlineItemOut): void => onOpen?.(i, TARGET[i.source_kind]);
  if (calendar === undefined)
    return <div data-screen="HOME-03" aria-busy="true" className="flex-1" />;
  const byId = new Map(calendar.items.map((i) => [i.filing_deadline_id, i]));
  const byDay = new Map<string, FilingDeadlineItemOut[]>();
  for (const i of calendar.items) byDay.set(i.due_on, [...(byDay.get(i.due_on) ?? []), i]);
  const days = new Map((calendar.days ?? []).map((d) => [d.on, d]));
  const start = new Date(`${calendar.window_from}T12:00:00Z`);
  const cells = Array.from({ length: 35 }, (_v, n) =>
    iso(new Date(start.getTime() + n * 86_400_000)),
  );
  const week = cells.slice(14, 21);
  return (
    <div data-screen="HOME-03" className="flex min-h-0 flex-1 flex-col">
      <div className="flex h-[42px] items-center gap-[8px] px-[12px]">
        <span className="text-[15px] font-medium text-ink">
          {COPY.title} <span className="font-normal text-ink-2">{COPY.context}</span>
        </span>
        <span className="flex flex-1 justify-center">
          <Segmented
            size="small"
            label={COPY.title}
            options={[...COPY.home]}
            active={COPY.home[2]}
          />
        </span>
      </div>
      <div className="flex h-[44px] items-center gap-[8px] px-[12px]">
        <span className="text-[15px] font-medium text-ink">{COPY.month}</span>
        <Button variant="secondary" size="sm">
          {COPY.today}
        </Button>
        <span className="flex flex-1 justify-center">
          <Segmented
            size="small"
            label={COPY.views.month}
            options={[COPY.views.month, COPY.views.week, COPY.views.list]}
            active={COPY.views[view]}
            {...(onView === undefined
              ? {}
              : {
                  onChange: (l: string) => {
                    onView(
                      (Object.keys(COPY.views) as Home03View[]).find((k) => COPY.views[k] === l) ??
                        "month",
                    );
                  },
                })}
          />
        </span>
        <span
          data-filter="person"
          className={`rounded-full px-[10px] py-[4px] text-[12.5px] ${person ? "bg-amber-tint text-amber-ink" : "bg-card text-ink-2 shadow-e1"}`}
        >
          {`${COPY.filters.person} │ ${person ?? COPY.filters.anyone}`}
        </span>
        <Button variant="ghost" size="sm" onClick={() => onExport?.("ics")}>
          {COPY.export}
        </Button>
      </div>
      <section
        aria-label={COPY.title}
        className="mx-[12px] flex min-h-0 flex-1 flex-col rounded-card bg-card shadow-e2"
      >
        {calendar.items.length === 0 ? (
          <p role="status" className="p-[24px] text-center text-body text-ink-2">
            {COPY.emptyFilter}
          </p>
        ) : view === "list" ? (
          <table aria-label={COPY.views.list} className="w-full text-body">
            <thead>
              <tr className="h-[30px] bg-nested text-left text-dense text-ink-2">
                {COPY.listColumns.map((c) => (
                  <th key={c} className="px-[8px] font-medium">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {calendar.items.map((i) => (
                <tr
                  key={i.filing_deadline_id}
                  data-list-row=""
                  className="h-[38px] border-t border-hair"
                >
                  <td className="px-[8px]">{short(i.due_on)}</td>
                  <td className="px-[8px]">
                    <button
                      type="button"
                      onClick={() => {
                        open(i);
                      }}
                    >
                      {i.client_name}
                    </button>
                  </td>
                  <td className="px-[8px]">{i.filing_label}</td>
                  <td className="px-[8px]">{i.rule_text ?? ""}</td>
                  <td className="px-[8px]">{i.stage_label}</td>
                  <td className="px-[8px]">{i.owners.map((o) => o.initials).join(" / ")}</td>
                  <td className="px-[8px]">
                    <Pill variant={TINT[i.risk]}>{i.risk_label}</Pill>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div
            className={`grid flex-1 ${view === "week" ? "grid-rows-[30px_1fr]" : "grid-rows-[30px_repeat(5,minmax(0,1fr))]"} grid-cols-7`}
          >
            {COPY.weekdays.map((w) => (
              <div
                key={w}
                className="bg-nested px-[10px] py-[8px] text-[11.5px] font-medium text-ink-3"
              >
                {w}
              </div>
            ))}
            {(view === "week" ? week : cells).map((d) => {
              const list = byDay.get(d) ?? [];
              const shown = (days.get(d)?.shown ?? [])
                .map((id) => byId.get(id))
                .filter((x): x is FilingDeadlineItemOut => x !== undefined);
              const chips = view === "week" ? list : shown;
              const rest = list.length - chips.length;
              const outside = !d.startsWith("2026-09");
              const isToday = d === calendar.today;
              return (
                <div
                  key={d}
                  data-day={d}
                  className="flex min-h-0 flex-col gap-[4px] border-t border-l border-hair p-[6px]"
                >
                  <span
                    className={`text-[12.5px] ${isToday ? "flex h-[22px] w-[22px] items-center justify-center rounded-full bg-ink text-shell" : outside ? "text-ink-4" : "text-ink-2"}`}
                  >
                    {String(Number(d.slice(8)))}
                  </span>
                  {chips.map((i) => (
                    <div key={i.filing_deadline_id}>
                      <Chip
                        item={i}
                        onOpen={open}
                        outside={outside}
                        detail={
                          detail?.item.filing_deadline_id === i.filing_deadline_id
                            ? detail
                            : undefined
                        }
                      />
                      {i.postponed_from ? (
                        <span className="block text-[11px] text-ink-3">
                          {COPY.postponedFrom(short(i.postponed_from))}
                        </span>
                      ) : null}
                    </div>
                  ))}
                  {rest > 0 ? (
                    <Popover
                      open={more === d}
                      onOpenChange={(o) => {
                        setMore(o ? d : undefined);
                      }}
                      width={300}
                      label={`${short(d)} · ${String(list.length)}`}
                      trigger={
                        <button
                          type="button"
                          className="text-left text-[11.5px] text-ink-3"
                          onClick={() => {
                            setMore(d);
                          }}
                        >
                          {COPY.more(rest)}
                        </button>
                      }
                    >
                      <ul data-day-popover="" className="flex flex-col gap-[4px] p-[10px]">
                        {list.map((i) => (
                          <li
                            key={i.filing_deadline_id}
                            className="flex items-center justify-between gap-[6px] text-body"
                          >
                            <button
                              type="button"
                              className="truncate text-left"
                              onClick={() => {
                                open(i);
                              }}
                            >
                              {`${i.client_name} · ${i.filing_label}`}
                            </button>
                            <Pill variant="neutral">{i.stage_label}</Pill>
                          </li>
                        ))}
                      </ul>
                    </Popover>
                  ) : null}
                </div>
              );
            })}
          </div>
        )}
        <p className="flex h-[26px] items-center border-t border-hair px-[12px] text-[11.5px] text-ink-3">
          {COPY.footer}
        </p>
      </section>
    </div>
  );
}

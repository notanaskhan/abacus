import { Button, Icon, type IconName, Segmented, StatusPill } from "@abacus/ui";
import { type JSX, useState } from "react";
import {
  BUILT_FROM,
  type CommRow,
  FIRST_ROW,
  INTERNAL_CONTROL,
  PLANNING,
  type PaperSection,
  RECIPIENTS,
  ROWS,
  SELECTED,
} from "./copy";

// AUD-22 · Governance communications in fixture mode on T10 (A-07-T29; handoff AUD-22): the
// required communications with their clocks, the TCWG recipients, what each letter was built from,
// and the paper of the selected letter (DRAFT until sent). "Approve & send…" is the engagement
// partner's (fresh MFA at the server, A-07-T26) and opens the send through `onApproveSend`;
// "Regenerate" keeps human edits (the server's section merge). Nothing here is agent-owned.

export type Frame = "a" | "b" | "c";

export interface GovernanceProps {
  frame: Frame;
  /** The viewer may approve and send (the server's `allowed_actions`). */
  canApproveSend?: boolean;
  onBack?: () => void;
  onApproveSend?: (key: string) => void;
  onRegenerate?: (key: string) => void;
  onBuiltFrom?: (source: string) => void;
}

const DISC: Readonly<Record<CommRow["disc"], IconName>> = {
  half: "circle-dot",
  ring: "circle",
  done: "circle-check",
};

function Section({ s }: { s: PaperSection }): JSX.Element {
  return (
    <>
      <h4 className="pt-[10px] text-[13.5px] font-medium">{s.heading}</h4>
      {s.body !== undefined && <p>{s.body}</p>}
      {s.bullets !== undefined && (
        <ul className="list-disc pl-[18px]">
          {s.bullets.map((b) => (
            <li key={b}>{b}</li>
          ))}
        </ul>
      )}
      {s.after !== undefined && <p>{s.after}</p>}
    </>
  );
}

/** AUD-22: the communications list and the selected letter. */
export function Governance(props: GovernanceProps): JSX.Element {
  const { frame } = props;
  const [tab, setTab] = useState<string>("Communications 5");
  const [selected, setSelected] = useState(SELECTED[frame]);
  const rows = ROWS[frame];
  const row = rows.find((r) => r.key === selected) ?? rows[0] ?? FIRST_ROW;
  const sent = row.tone === "success";
  const paper =
    selected === "sd_mw_265" || selected === "reportable_703" ? INTERNAL_CONTROL : PLANNING;
  return (
    <div data-screen="AUD-22" data-frame={frame} className="flex min-h-0 flex-1 flex-col">
      <div className="flex h-[50px] items-center px-[12px]">
        <Button size="sm" variant="ghost" onClick={props.onBack}>
          ‹ Cockpit
        </Button>
        <div className="flex flex-1 justify-center">
          <Segmented
            size="small"
            label="Governance views"
            options={["Communications 5", "Recipients", "History"]}
            active={tab}
            onChange={setTab}
          />
        </div>
      </div>
      <div className="flex min-h-0 flex-1 gap-[10px] px-[12px] pb-[12px]">
        <section
          aria-label="Structure"
          className="w-[470px] shrink-0 overflow-y-auto rounded-pane bg-card shadow-e1"
        >
          <h2 className="flex h-[32px] items-center px-[12px] text-[12.5px] font-medium text-ink-2">
            Governance communications › Northwind Robotics 401(k) Plan
          </h2>
          <h3 className="flex h-[31px] items-center bg-band-hd px-[12px] text-dense font-medium">
            Required communications
          </h3>
          <ul>
            {rows.map((r) => (
              <li key={r.key}>
                <button
                  type="button"
                  data-comm-row={r.key}
                  aria-current={r.key === selected ? "true" : undefined}
                  className={`flex min-h-[52px] w-full items-center gap-2 px-[12px] text-left ${r.key === selected ? "bg-sel-bg" : ""}`}
                  onClick={() => {
                    setSelected(r.key);
                  }}
                >
                  <Icon name={DISC[r.disc]} size={15} />
                  <span className="min-w-0 flex-1">
                    <span className="block text-[13px] font-medium">{r.title}</span>
                    <span className="block text-[11.5px] text-ink-3">{r.note ?? r.sub}</span>
                  </span>
                  <span className="flex flex-col items-end gap-1">
                    <StatusPill tone={r.tone}>{r.pill}</StatusPill>
                    {r.note === "Awaiting EP approval" && (
                      <span className="text-[11px] text-amber-ink">{r.note}</span>
                    )}
                    {r.due !== undefined && (
                      <span className="rounded-pill bg-amber-tint px-[6px] text-[11px] text-amber-ink">
                        {r.due}
                      </span>
                    )}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <h3 className="flex h-[31px] items-center bg-band-hd px-[12px] text-dense font-medium">
            Recipients (TCWG)
          </h3>
          <dl className="px-[12px] py-[4px] text-[13px]">
            {RECIPIENTS.map(([k, v]) => (
              <div key={k} className="flex h-[33px] items-center justify-between gap-2">
                <dt className="text-ink-2">{k}</dt>
                <dd>
                  {v} <span className="text-ink-3">→</span>
                </dd>
              </div>
            ))}
          </dl>
          <h3 className="flex h-[31px] items-center bg-band-hd px-[12px] text-dense font-medium">
            Built from
          </h3>
          <ul className="px-[12px] pb-[8px] text-[13px]">
            {BUILT_FROM.map((b) => (
              <li key={b} className="flex h-[33px] items-center">
                <button type="button" onClick={() => props.onBuiltFrom?.(b)}>
                  {b} <span className="text-ink-3">→</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
        <section aria-label="Paper" className="flex min-w-0 flex-1 flex-col rounded-pane bg-shell">
          <header className="relative flex h-[46px] items-center justify-center">
            <h2 className="text-[14.5px] font-medium">{paper.title}</h2>
            {sent ? (
              <span className="absolute right-[10px]" aria-label="Locked">
                <Icon name="lock" size={12} />
              </span>
            ) : (
              <div className="absolute right-[10px] flex gap-2">
                <Button size="sm" variant="secondary">
                  Edit
                </Button>
                <Button size="sm" variant="ghost" onClick={() => props.onRegenerate?.(selected)}>
                  <Icon name="refresh-cw" size={14} />
                  Regenerate
                </Button>
                {props.canApproveSend === true && (
                  <Button size="sm" onClick={() => props.onApproveSend?.(selected)}>
                    Approve &amp; send…
                  </Button>
                )}
              </div>
            )}
          </header>
          <div className="min-h-0 flex-1 overflow-y-auto p-[14px]">
            <article className="relative mx-auto w-[600px] overflow-hidden rounded-pane bg-card px-[24px] pb-[24px] pt-[20px] text-[12px] leading-[1.55] shadow-e2">
              {!sent && (
                <span
                  aria-hidden="true"
                  data-watermark="draft"
                  className="pointer-events-none absolute inset-0 flex -rotate-[30deg] items-center justify-center text-[72px] font-medium text-ink/[.06]"
                >
                  DRAFT
                </span>
              )}
              <p className="text-[13.5px] font-medium">Brightwater Hale LLP</p>
              <p className="text-[11.5px] text-ink-3">311 West Brannock Street, Chicago, IL</p>
              <hr className="my-[8px] border-hair" />
              {paper === PLANNING && (
                <>
                  <p>{PLANNING.date}</p>
                  <p className="pb-[8px]">{PLANNING.addressee}</p>
                </>
              )}
              <h3 className="text-[16px] font-medium">{paper.h3}</h3>
              {paper.sections.map((s) => (
                <Section key={s.heading} s={s} />
              ))}
              {paper === PLANNING && <p className="pt-[14px] font-medium">{PLANNING.signature}</p>}
            </article>
          </div>
        </section>
      </div>
    </div>
  );
}

// AUD-22 on the server's data (A-07-T29 remainder; DEC-3144): the work item's communications from
// A-07-T26's list and the selected letter's composed sections, behind `audits.letters`. No artboard
// words: row titles are the screen's labels, statuses the vocabulary's, the paper the letter's own
// sections. "Approve & send…" shows only with the server's `governance_comm.approve_send` and stays
// the engagement partner's (fresh second factor at the server).
import type { GovernanceCommunicationOut, GovernanceListOut } from "@abacus/api-client";
import { Button, Icon, type IconName, RegistryStatus } from "@abacus/ui";
import type { JSX } from "react";
import { KIND_ROW } from "./copy";

const DISC: Readonly<Record<string, IconName>> = {
  not_started: "circle",
  draft: "circle-dot",
  awaiting_ep_approval: "circle-dot",
  sent: "circle-check",
  acknowledged: "circle-check",
};

export interface GovernanceLiveProps {
  list: GovernanceListOut;
  letter: GovernanceCommunicationOut | undefined;
  selected: string | null;
  onSelect: (communicationId: string) => void;
  onBack?: () => void;
  onApproveSend?: (communicationId: string) => void;
  onRegenerate?: (communicationId: string) => void;
}

export function GovernanceLive(props: GovernanceLiveProps): JSX.Element {
  const { list, letter } = props;
  // A control shows only when the host binds it (the send dialog with its fresh second factor
  // and regenerate land with their wiring); never a button that does nothing.
  const canSend =
    letter?.allowed_actions.includes("governance_comm.approve_send") === true &&
    props.onApproveSend !== undefined;
  const canRegenerate = props.onRegenerate !== undefined;
  return (
    <div data-screen="AUD-22" data-live="true" className="flex min-h-0 flex-1 flex-col">
      <div className="flex h-[50px] items-center px-[12px]">
        <Button size="sm" variant="ghost" onClick={props.onBack}>
          ‹ Cockpit
        </Button>
      </div>
      <div className="flex min-h-0 flex-1 gap-[10px] px-[12px] pb-[12px]">
        <section
          aria-label="Structure"
          className="w-[470px] shrink-0 overflow-y-auto rounded-pane bg-card shadow-e1"
        >
          <h3 className="flex h-[31px] items-center bg-band-hd px-[12px] text-dense font-medium">
            Required communications
          </h3>
          <ul>
            {list.items.map((r) => (
              <li key={r.id}>
                <button
                  type="button"
                  data-comm-row={r.kind}
                  aria-current={r.id === props.selected ? "true" : undefined}
                  className={`flex min-h-[52px] w-full items-center gap-2 px-[12px] text-left ${r.id === props.selected ? "bg-sel-bg" : ""}`}
                  onClick={() => {
                    props.onSelect(r.id);
                  }}
                >
                  <Icon name={DISC[r.status] ?? "circle"} size={15} />
                  <span className="min-w-0 flex-1">
                    <span className="block text-[13px] font-medium">
                      {KIND_ROW[r.kind]?.title ?? r.standard}
                    </span>
                    <span className="block text-[11.5px] text-ink-3">{r.standard}</span>
                  </span>
                  <RegistryStatus
                    object="governance_communication"
                    code={r.overdue ? "overdue" : r.status}
                    withDisc={false}
                  />
                </button>
              </li>
            ))}
          </ul>
        </section>
        <section aria-label="Paper" className="flex min-w-0 flex-1 flex-col rounded-pane bg-shell">
          <header className="relative flex h-[46px] items-center justify-center">
            <h2 className="text-[14.5px] font-medium">
              {letter === undefined
                ? ""
                : (KIND_ROW[letter.row.kind]?.title ?? letter.row.standard)}
            </h2>
            {letter !== undefined && letter.watermark === "draft" && (
              <div className="absolute right-[10px] flex gap-2">
                {canRegenerate && (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => props.onRegenerate?.(letter.row.id)}
                  >
                    <Icon name="refresh-cw" size={14} />
                    Regenerate
                  </Button>
                )}
                {canSend && (
                  <Button size="sm" onClick={() => props.onApproveSend?.(letter.row.id)}>
                    Approve &amp; send…
                  </Button>
                )}
              </div>
            )}
          </header>
          <div
            // A scrolling region is reachable by keyboard (axe scrollable-region-focusable).
            tabIndex={0}
            role="region"
            aria-label="Paper content"
            className="min-h-0 flex-1 overflow-y-auto p-[14px]"
          >
            {letter !== undefined && (
              <article className="relative mx-auto w-[600px] overflow-hidden rounded-pane bg-card px-[24px] pb-[24px] pt-[20px] text-[12px] leading-[1.55] shadow-e2">
                {letter.watermark === "draft" && (
                  <span
                    aria-hidden="true"
                    data-watermark="draft"
                    className="pointer-events-none absolute inset-0 flex -rotate-[30deg] items-center justify-center text-[72px] font-medium text-ink/[.06] before:content-['DRAFT']"
                  />
                )}
                {letter.sections.map((s) => (
                  <section key={s.key} data-section={s.key}>
                    {s.title !== "" && (
                      <h4 className="pt-[10px] text-[13.5px] font-medium">{s.title}</h4>
                    )}
                    <p className="whitespace-pre-line">{s.text}</p>
                  </section>
                ))}
              </article>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

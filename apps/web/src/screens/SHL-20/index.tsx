// SHL-20 Evidence screening (P-06-T22; docs/screens/SHL-20.md): the C-34 card in local state
// (chapter 04 §2.4), opened from the screening chip on an upload row and closed by the chip, ✕ or
// Escape; closing gives focus back to the chip (P-06 §5.6; ED-090).
// This frame draws the upload row the card hangs from (the hosts are BND-02 here, AUD-03 with
// A-01, CLS-03 with C-01) and the ScreeningCardHost under it; the O3 follow-up sheet, the
// ReturnDialog and "View" → SHL-08 open from the card.

import type { ScreeningCardOut } from "@abacus/api-client";
import { Icon, Pill, registryWord } from "@abacus/ui";
import { type JSX, type KeyboardEvent, useRef, useState } from "react";
import {
  ScreeningCardHost,
  type ScreeningSubjectRef,
  UnlinkedScreeningCard,
  chipText,
  useScreeningCard,
} from "../../domain/screening";

export interface EvidenceScreeningProps {
  /** The request whose upload is screened; null for a file not linked to one (e). */
  subject: ScreeningSubjectRef | null;
  /** e: the unlinked file's name. */
  file?: string;
  /** Open "Why?" (f) or the follow-up draft (b) as the frame opens. */
  open?: "feedback" | "follow-up";
}

const CHIP: Record<ScreeningCardOut["verdict"], string> = {
  flagged: "bg-amber-tint text-amber-ink",
  passed: "bg-green-tint text-green-ink",
  not_screened: "bg-nested text-ink-3",
};

function ScreeningChip({
  card,
  shown,
  onToggle,
}: {
  card: Pick<ScreeningCardOut, "verdict" | "file_flags">;
  shown: boolean;
  onToggle: () => void;
}): JSX.Element {
  return (
    <button
      type="button"
      aria-expanded={shown}
      onClick={onToggle}
      data-screening-chip={card.verdict}
      className={`inline-flex h-[22px] w-fit items-center gap-[5px] rounded-pill px-[8px] text-pill-sm ${CHIP[card.verdict]}`}
    >
      {card.verdict === "flagged" && <Icon name="triangle-alert" size={12} aria-hidden />}
      {chipText(card)}
    </button>
  );
}

export function EvidenceScreening({ subject, file, open }: EvidenceScreeningProps): JSX.Element {
  const [shown, setShown] = useState(true);
  const card = useScreeningCard(subject).data;
  const frame = useRef<HTMLDivElement>(null);
  const toggle = (): void => {
    setShown((s) => !s);
  };
  const close = (): void => {
    setShown(false);
    frame.current?.querySelector<HTMLElement>("[data-screening-chip]")?.focus();
  };
  // Escape closes the non-modal card from anywhere in this frame. An overlay the card opened (the
  // ReturnDialog, "Why?", the O3 sheet) is portalled outside the frame and handles its own Escape.
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>): void => {
    if (event.key !== "Escape" || !shown || event.defaultPrevented) return;
    if (!(event.target instanceof Node) || frame.current?.contains(event.target) !== true) return;
    event.preventDefault();
    close();
  };
  const unlinked = subject === null;
  return (
    <div
      ref={frame}
      data-screen="SHL-20"
      onKeyDown={onKeyDown}
      className="flex flex-col gap-[8px] p-[12px]"
    >
      <div className="flex w-[536px] flex-col gap-[6px] rounded-pane bg-card px-[16px] py-[12px] shadow-e2">
        <div className="flex items-start gap-[10px]">
          <Icon
            name={unlinked ? "file-text" : "folder"}
            size={14}
            className="mt-[2px] text-ink-3"
          />
          <span className="min-w-0 flex-1 text-body font-medium">
            {unlinked ? file : card?.request_title}
          </span>
          {!unlinked && (
            <Pill variant="amber" size="state">
              {registryWord("request", "uploaded").label}
            </Pill>
          )}
        </div>
        {card !== undefined && !unlinked && (
          <span className="pl-[24px]">
            <ScreeningChip card={card} shown={shown} onToggle={toggle} />
          </span>
        )}
        {unlinked && (
          <span className="pl-[24px]">
            <ScreeningChip
              card={{ verdict: "not_screened", file_flags: [] }}
              shown={shown}
              onToggle={toggle}
            />
          </span>
        )}
      </div>
      {shown &&
        (subject === null ? (
          <UnlinkedScreeningCard onClose={close} />
        ) : (
          <ScreeningCardHost
            subject={subject}
            onClose={close}
            {...(open === undefined ? {} : { open })}
          />
        ))}
    </div>
  );
}

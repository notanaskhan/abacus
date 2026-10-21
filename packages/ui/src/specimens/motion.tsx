import { type JSX, useState } from "react";
import { AgentText } from "../agent-text";
import { LiveDot, Pulse, Reveal, SPINNER_SIZES, Spinner, TypingDots } from "../components/motion";
import { useReducedMotion, useWordReveal } from "../motion";
import { Row, Sheet } from "./frame";

// The motion primitives' specimens (F-05-T14): Spinner and Pulse from C-20 States and Foundations
// 04, Reveal and TypingDots from C-10 Chat. Every size and both forms are drawn: the running form,
// which the system's reduced-motion preference turns into the still one, and the still form
// itself (`still`), so the reduced-motion look is always on the page. Sample text is the chat
// kit's own line.

const SAMPLE_LINE =
  "I’ll start with read-only discovery of returns, engagements and office assignments.";

function ReducedNote(): JSX.Element {
  const reduced = useReducedMotion();
  return (
    <span className="text-meta text-ink-3" data-testid="reduced-motion-state">
      {reduced ? "Reduced motion is on: every form below is still." : "Motion is on."}
    </span>
  );
}

function ReplayButton({ onClick }: { onClick: () => void }): JSX.Element {
  return (
    <button
      type="button"
      onClick={onClick}
      className="h-[26px] rounded-pill bg-nested px-[11px] text-btn-sm text-ink hover:bg-sel-bg"
    >
      Replay
    </button>
  );
}

export function SpinnerSpecimen(): JSX.Element {
  return (
    <Sheet title="Spinners" meta="820ms linear · 28% arc · stroke 1.5">
      <Row name="Motion preference" meaning="Read by useReducedMotion()">
        <ReducedNote />
      </Row>
      {SPINNER_SIZES.map((size) => (
        <Row
          key={size}
          name={`${String(size)}px`}
          meaning={size === 10 ? "Pill and chip" : size === 12 ? "28px control" : "Disc"}
        >
          <Spinner size={size} label="Loading" />
          <Spinner size={size} label="Loading" showLabel={false} />
          <Spinner size={size} label="Loading, still" still />
        </Row>
      ))}
    </Sheet>
  );
}

export function PulseSpecimen(): JSX.Element {
  return (
    <Sheet title="Pulse" meta="Skeleton 1.2s · rows 70ms apart · live dot 2.4s">
      <Row name="Skeleton rows" meaning="Real row heights, 9h and 7h bars, no shimmer">
        <div className="flex w-[260px] flex-col gap-2">
          {[0, 1, 2].map((i) => (
            <Pulse key={i} index={i} className="flex flex-col gap-[6px]">
              <span className="block h-[9px] w-[62%] rounded-[4.5px] bg-nested" />
              <span className="block h-[7px] w-[38%] rounded-[3.5px] bg-nested" />
            </Pulse>
          ))}
        </div>
      </Row>
      <Row name="Skeleton, still" meaning="Reduced motion">
        <div className="flex w-[260px] flex-col gap-2">
          {[0, 1, 2].map((i) => (
            <Pulse key={i} index={i} still className="flex flex-col gap-[6px]">
              <span className="block h-[9px] w-[62%] rounded-[4.5px] bg-nested" />
              <span className="block h-[7px] w-[38%] rounded-[3.5px] bg-nested" />
            </Pulse>
          ))}
        </div>
      </Row>
      <Row name="Live dot" meaning="Pane header while anything runs">
        <span className="inline-flex items-center gap-[8px] text-dense text-ink-2">
          <LiveDot />
          Running
        </span>
        <span className="inline-flex items-center gap-[8px] text-dense text-ink-2">
          <LiveDot still />
          Running, still
        </span>
      </Row>
    </Sheet>
  );
}

/** Mounted under a new key to play again; agent text goes through AgentText even when partial. */
function WordRevealDemo(): JSX.Element {
  const { text } = useWordReveal(SAMPLE_LINE);
  return (
    <div className="w-[360px] text-chat">
      <AgentText text={text} />
    </div>
  );
}

export function RevealSpecimen(): JSX.Element {
  const [run, setRun] = useState(0);
  return (
    <Sheet title="Reveal" meta="260ms · opacity and a 6px rise · words 20ms">
      <Row name="Block" meaning="A new row or message">
        <div key={run} className="flex w-[360px] flex-col gap-2">
          <Reveal className="rounded-nested bg-card px-3 py-2 text-chat shadow-e1">
            First block
          </Reveal>
          <Reveal delay={260} className="rounded-nested bg-card px-3 py-2 text-chat shadow-e1">
            A block after the paragraph before it
          </Reveal>
        </div>
        <ReplayButton
          onClick={() => {
            setRun((n) => n + 1);
          }}
        />
      </Row>
      <Row name="Block, still" meaning="Reduced motion: at once">
        <Reveal still className="w-[360px] rounded-nested bg-card px-3 py-2 text-chat shadow-e1">
          First block
        </Reveal>
      </Row>
      <Row name="Words" meaning="Over complete, verified text">
        <WordRevealDemo key={run} />
      </Row>
    </Sheet>
  );
}

export function TypingDotsSpecimen(): JSX.Element {
  return (
    <Sheet title="Typing dots" meta="39h bubble · 5px dots · 1.1s · 150ms apart">
      <Row name="Typing" meaning="Agent is preparing a line">
        <TypingDots label="Typing" />
        <TypingDots label="Typing, no bubble" bubble={false} />
      </Row>
      <Row name="Typing, still" meaning="Reduced motion">
        <TypingDots label="Typing, still" still />
      </Row>
    </Sheet>
  );
}

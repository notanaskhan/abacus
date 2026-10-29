import type { JSX } from "react";
import { cn } from "../cn";
import { RING_CIRCUMFERENCE, RING_RADIUS, ringView } from "../components/progress-model";
import { Icon } from "../icons";
import type { IconName } from "../icons/names";
import { PRESS } from "../components/control-classes";

// The T7-M home cards (F-06-T10; TPL-19 frame 1; POR-02 at 390): the greeting, the return card
// with its progress ring, the to-do card and the team card, one column of white cards on the
// shell. White-labelled like the rest of the portal: the firm's name, never the product's. Every
// row is at least 44 high (F-05 accessibility on portal mobile).

export function MobileGreeting({ text }: { text: string }): JSX.Element {
  return <h1 className="px-[4px] pt-[4px] text-dashboard font-medium">{text}</h1>;
}

export interface ReturnProgressCardProps {
  /** "2025 Tax Return". */
  title: string;
  /** 0 to 1: the share of requested documents received. */
  fraction: number;
  /** "We're reviewing your return". */
  status: string;
  /** "2 documents still needed · extended due date Oct 15, 2026". */
  line: string;
}

/** The return card: a 40px ring (amber arc on a hair track) beside the status and its line. */
export function ReturnProgressCard({
  title,
  fraction,
  status,
  line,
}: ReturnProgressCardProps): JSX.Element {
  const view = ringView(fraction);
  return (
    <section
      aria-label={title}
      className="flex flex-none flex-col gap-[10px] rounded-pane bg-card px-[14px] py-[12px] shadow-e1"
    >
      <h2 className="text-section">{title}</h2>
      <div className="flex items-center gap-[12px]">
        <svg
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={view.valueNow}
          aria-label={status}
          viewBox="0 0 50 50"
          className="size-[40px] flex-none -rotate-90"
        >
          <circle
            cx={25}
            cy={25}
            r={RING_RADIUS}
            fill="none"
            strokeWidth={3}
            className="stroke-hair"
          />
          {view.arc && (
            <circle
              cx={25}
              cy={25}
              r={RING_RADIUS}
              fill="none"
              strokeWidth={3}
              strokeLinecap="round"
              strokeDasharray={RING_CIRCUMFERENCE}
              strokeDashoffset={view.offset}
              className="stroke-amber"
            />
          )}
        </svg>
        <span className="flex min-w-0 flex-col gap-[3px]">
          <span className="text-body font-medium">{status}</span>
          <span className="text-cell text-ink-2">{line}</span>
        </span>
      </div>
    </section>
  );
}

export interface MobileTodo {
  key: string;
  icon: IconName;
  title: string;
  detail?: string;
  onOpen?: () => void;
}

/** The to-do card: 52 rows, a glyph, the title (and a quoted line), a chevron. */
export function MobileTodoCard({
  label,
  items,
}: {
  label: string;
  items: readonly MobileTodo[];
}): JSX.Element {
  return (
    <section
      aria-label={label}
      className="flex-none overflow-hidden rounded-pane bg-card shadow-e1"
    >
      {items.map((t, i) => (
        <button
          key={t.key}
          type="button"
          onClick={t.onOpen}
          className={cn(
            "flex min-h-[52px] w-full items-center gap-[10px] px-[14px] py-[8px] text-left",
            i > 0 && "hairline-t",
            PRESS,
          )}
        >
          <Icon name={t.icon} size={18} className="flex-none text-ink-2" />
          <span className="flex min-w-0 flex-1 flex-col gap-[2px]">
            <span className="truncate text-body font-medium">{t.title}</span>
            {t.detail !== undefined && (
              <span className="truncate text-pill font-normal text-ink-3">{t.detail}</span>
            )}
          </span>
          <Icon name="chevron-right" size={16} className="flex-none text-ink-3" />
        </button>
      ))}
    </section>
  );
}

export interface TeamMember {
  name: string;
  role: string;
}

/** "Your Brightwater Hale team": who works on the return, name over role. */
export function MobileTeamCard({
  title,
  people,
}: {
  title: string;
  people: readonly TeamMember[];
}): JSX.Element {
  return (
    <section
      aria-label={title}
      className="flex flex-none flex-col rounded-pane bg-card px-[14px] py-[10px] shadow-e1"
    >
      <h2 className="pb-[4px] text-section">{title}</h2>
      <ul className="flex flex-col">
        {people.map((p) => (
          <li key={p.name} className="flex min-h-[44px] flex-col justify-center gap-[2px]">
            <span className="text-body">{p.name}</span>
            <span className="text-meta text-ink-3">{p.role}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

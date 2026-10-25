import type { JSX } from "react";
import { cn } from "../cn";
import { Pill } from "../components/pill";
import { TallyPill } from "../components/status";
import { Icon } from "../icons";
import { useMotion } from "../motion";
import type { PillVariant, RegistryCode } from "../status";

// TallyStrip (C-01 spec 06; F-05-T43): the row of check cards over a workbook or a workpaper
// ("CAPITAL FOOTS · Ties", "K-1s ISSUED · 3 / 4"). Each card is 52 tall, white e1, radius 10, an
// uppercase 9.5 label over one second line: a value, a tally pill, or green sign-off chips, with an
// optional text link. The pills' words are the status registry's (`tie_out_tally`); a running
// check is the tag pill with its spinner. Cards enter with the 260ms reveal, 45ms apart. Every
// figure is the server's; the strip computes nothing.

export const TALLY_STAGGER_MS = 45;

export type TallyCode = RegistryCode<"tie_out_tally">;

interface TallyBase {
  /** Uppercase on the card: "CAPITAL FOOTS". */
  label: string;
  /** A text link after the second line ("Open M-1"). */
  link?: { text: string; onClick: () => void };
}

/** A pill on a card: after a value ("46 of 46" · "Full", ADM-02a) or as the second line itself
 * (SIGN-IN "SSO + MFA 46 of 46", green with a check). */
export interface TallyPillSpec {
  text: string;
  variant: PillVariant;
  check?: boolean;
}

export type TallyItem =
  | (TallyBase & { value: string; info?: string; pill?: TallyPillSpec })
  | (TallyBase & { pill: TallyPillSpec })
  | (TallyBase & { tally: TallyCode; vars?: Readonly<Record<string, string | number>> })
  | (TallyBase & { running: string })
  | (TallyBase & { signs: readonly { initials: string; when?: string; name: string }[] });

function TallyPillOf({ pill }: { pill: TallyPillSpec }): JSX.Element {
  return (
    <Pill variant={pill.variant} size="sm" {...(pill.check === true ? { check: true } : {})}>
      {pill.text}
    </Pill>
  );
}

function Second({ item }: { item: TallyItem }): JSX.Element {
  if ("value" in item) {
    return (
      <span className="flex items-center gap-[6px]">
        <span className="text-title font-normal tracking-[-0.01em] tabular-nums">
          {item.value}
        </span>
        {item.info !== undefined && (
          <span role="img" aria-label={item.info} title={item.info} className="cursor-help">
            <Icon name="info" size={15} className="text-ink-3" />
          </span>
        )}
        {item.pill !== undefined && <TallyPillOf pill={item.pill} />}
      </span>
    );
  }
  if ("pill" in item) return <TallyPillOf pill={item.pill} />;
  if ("tally" in item) {
    return (
      <TallyPill code={item.tally} {...(item.vars === undefined ? {} : { vars: item.vars })} />
    );
  }
  if ("running" in item) {
    return (
      <Pill variant="tag" size="tally" spin>
        {item.running}
      </Pill>
    );
  }
  return (
    <span className="flex flex-wrap items-center gap-[4px]">
      {item.signs.map((sign) => (
        <Pill
          key={`${sign.initials}:${sign.when ?? ""}`}
          variant="green"
          size="tally"
          check
          title={`Signed off by ${sign.name}${sign.when === undefined ? "" : ` · ${sign.when}`}`}
        >
          {sign.when === undefined ? sign.initials : `${sign.initials} · ${sign.when}`}
        </Pill>
      ))}
    </span>
  );
}

export interface TallyStripProps {
  items: readonly TallyItem[];
  /** The strip's accessible name. */
  label?: string;
  className?: string;
}

export function TallyStrip({ items, label = "Checks", className }: TallyStripProps): JSX.Element {
  const animate = useMotion();
  return (
    <ul aria-label={label} data-tally-strip="" className={cn("flex gap-[8px]", className)}>
      {items.map((item, i) => (
        <li
          key={item.label}
          style={animate ? { animationDelay: `${String(i * TALLY_STAGGER_MS)}ms` } : undefined}
          className={cn(
            "flex h-[52px] min-w-0 flex-[1_1_0%] flex-col justify-between rounded-nested bg-card px-[12px] py-[8px] shadow-e1",
            animate && "motion-reveal",
          )}
        >
          <span className="truncate text-kpi-label text-ink-3 uppercase">{item.label}</span>
          <span className="flex min-w-0 items-center gap-[8px]">
            <Second item={item} />
            {item.link !== undefined && (
              <button
                type="button"
                onClick={item.link.onClick}
                className="inline-flex items-center gap-[2px] text-meta font-medium text-ink hover:underline"
              >
                {item.link.text}
                <span aria-hidden="true" className="text-ink-3">
                  ›
                </span>
              </button>
            )}
          </span>
        </li>
      ))}
    </ul>
  );
}

import type { JSX, ReactNode } from "react";
import { cn } from "../cn";
import { Pill } from "../components/pill";
import { StatusDisc } from "../components/status";
import { Tooltip } from "../components/popover";
import { Icon, type IconName } from "../icons";

// The O6 wizard's kit (TPL-18, F-05-T38; Wave 0 - Templates `#tpl18`): the data-driven type
// catalogue and the gate cards a screen puts in a Wizard step (ENG-03, CLI-06).
//
// The catalogue draws only what it is given. The groups, their types and which entitlement each
// type needs are data (the screen reads `GET /v1/engagement-types`, ENG-03); a type the firm is not
// entitled to, and a type the data marks `comingSoon` (Single audit, D1 and D10), render as the
// "Coming soon" card and cannot be picked, whatever the entitlements say for the latter.

/** A group's icon tile colour (02 A8.18): clay for tax, espresso for assurance, olive for
 * accounting, ochre for advisory and other. */
export type CatalogueTone = "clay" | "espresso" | "green" | "amber";

export interface CatalogueType {
  id: string;
  label: string;
  /** The ink-3 line under the name. */
  sub?: string;
  /** The entitlement the firm needs before the type can be picked (`attest` for SOC and AUP). */
  entitlement?: string;
  /** Never offered in this release: always the "Coming soon" card (Single audit). */
  comingSoon?: boolean;
}

export interface CatalogueGroup {
  id: string;
  label: string;
  tone: CatalogueTone;
  icon: IconName;
  types: readonly CatalogueType[];
}

export type TypeAvailability = "available" | "coming-soon";

/** Whether a type can be picked: never when the data says coming soon; otherwise only with its
 * entitlement, if it names one. */
export function typeAvailability(
  type: CatalogueType,
  entitlements: Iterable<string>,
): TypeAvailability {
  if (type.comingSoon === true) return "coming-soon";
  if (type.entitlement === undefined) return "available";
  for (const held of entitlements) if (held === type.entitlement) return "available";
  return "coming-soon";
}

const TILE: Record<CatalogueTone, string> = {
  clay: "bg-clay",
  espresso: "bg-espresso",
  green: "bg-green",
  amber: "bg-amber",
};

export interface TypeCardProps {
  type: CatalogueType;
  tone: CatalogueTone;
  icon: IconName;
  availability: TypeAvailability;
  selected?: boolean;
  onSelect?: () => void;
  soonLabel: string;
  /** The tooltip on a coming-soon card. */
  soonHint?: string;
}

/** One type card (the arc-agents card grammar): 88 high, white on e1, radius 12, a 30px icon tile,
 * a 13.5/500 name and an ink-3 line. Selected: a 1.5px espresso inset and an olive check disc.
 * Coming soon: nested, ink-4, the soon pill, and no press. */
export function TypeCard({
  type,
  tone,
  icon,
  availability,
  selected = false,
  onSelect,
  soonLabel,
  soonHint,
}: TypeCardProps): JSX.Element {
  const soon = availability === "coming-soon";
  const body = (
    <>
      <span className="flex items-start justify-between gap-[8px]">
        <span
          aria-hidden="true"
          className={cn(
            "inline-flex size-[30px] shrink-0 items-center justify-center rounded-tile text-on-dark",
            soon ? "bg-surface-deep" : TILE[tone],
          )}
        >
          <Icon name={icon} size={15} />
        </span>
        {soon ? (
          <Pill variant="soon" size="sm">
            {soonLabel}
          </Pill>
        ) : (
          selected && <StatusDisc state="done" size={16} />
        )}
      </span>
      <span className="mt-auto flex min-w-0 flex-col">
        <span className={cn("text-section", soon ? "text-ink-4" : "truncate text-ink")}>
          {type.label}
        </span>
        {type.sub !== undefined && type.sub !== "" && (
          <span className={cn("truncate text-meta", soon ? "text-ink-4" : "text-ink-3")}>
            {type.sub}
          </span>
        )}
      </span>
    </>
  );
  const box = "flex h-[88px] min-w-0 flex-col gap-[6px] rounded-pane p-[12px] text-left";
  if (soon) {
    const card = (
      <div
        data-type={type.id}
        data-availability="coming-soon"
        aria-disabled="true"
        tabIndex={soonHint === undefined ? undefined : 0}
        className={cn(box, "bg-nested")}
      >
        {body}
      </div>
    );
    return soonHint === undefined ? card : <Tooltip content={soonHint}>{card}</Tooltip>;
  }
  return (
    <button
      type="button"
      data-type={type.id}
      data-availability="available"
      aria-pressed={selected}
      onClick={onSelect}
      className={cn(
        box,
        "bg-card shadow-e1 transition-shadow duration-[180ms] hover:shadow-e2",
        selected && "inset-ring-[1.5px] inset-ring-espresso",
      )}
    >
      {body}
    </button>
  );
}

export interface TypeCatalogueProps {
  groups: readonly CatalogueGroup[];
  /** The firm's entitlements (`attest`, `group_audit`). */
  entitlements: Iterable<string>;
  selected?: string | null;
  /** A press on an available card: its id, or null when the selected card is pressed again. */
  onSelect?: (id: string | null) => void;
  /** "What kind of engagement?" */
  heading?: string;
  soonLabel?: string;
  soonHint?: string;
  className?: string;
}

/** The type catalogue: a heading, then each group's band and a four-column grid of type cards. */
export function TypeCatalogue({
  groups,
  entitlements,
  selected = null,
  onSelect,
  heading,
  soonLabel = "Coming soon",
  soonHint,
  className,
}: TypeCatalogueProps): JSX.Element {
  const held = [...entitlements];
  return (
    <div className={cn("flex flex-col", className)}>
      {heading !== undefined && (
        <h3 className="pt-[2px] pb-[6px] text-title font-medium tracking-[-0.012em]">{heading}</h3>
      )}
      {groups.map((group) => (
        <section
          key={group.id}
          aria-label={group.label}
          data-group={group.id}
          className="flex flex-col"
        >
          <h4 className="pt-[6px] pb-[8px] text-dense text-ink-2">{group.label}</h4>
          <div className="grid grid-cols-[repeat(4,170px)] gap-[12px]">
            {group.types.map((type) => (
              <TypeCard
                key={type.id}
                type={type}
                tone={group.tone}
                icon={group.icon}
                availability={typeAvailability(type, held)}
                selected={selected === type.id}
                onSelect={() => {
                  onSelect?.(selected === type.id ? null : type.id);
                }}
                soonLabel={soonLabel}
                {...(soonHint === undefined ? {} : { soonHint })}
              />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

// ---- Gate cards ---------------------------------------------------------------------------------

/** met: an olive check on a white card; needs: the amber card with a triangle; blocked: the brick
 * card with a cross. Words carry the meaning; the colour only repeats it. */
export type GateTone = "met" | "needs" | "blocked";

export interface GateCardProps {
  tone: GateTone;
  children: ReactNode;
  /** A secondary button at the right ("Request consent with the letter"). */
  action?: ReactNode;
  /** A link under the words ("Start acceptance (CLI-07) →"). */
  link?: ReactNode;
  className?: string;
}

const GATE_BOX: Record<GateTone, string> = {
  met: "bg-card shadow-e1 text-ink",
  needs: "bg-amber-tint text-amber-ink",
  blocked: "bg-card text-red-ink inset-ring-1 inset-ring-red-ink/40",
};

/** A gate on a wizard step (TPL-18): words first, with a disc or triangle beside them. Only a
 * `blocked` gate stops Create; the screen disables Create itself, from the same data. */
export function GateCard({ tone, children, action, link, className }: GateCardProps): JSX.Element {
  return (
    <div
      role={tone === "met" ? undefined : "status"}
      data-gate={tone}
      className={cn(
        "flex items-start gap-[10px] rounded-nested px-[14px] py-[11px] text-body",
        GATE_BOX[tone],
        className,
      )}
    >
      <span className="flex h-[19px] shrink-0 items-center">
        {tone === "met" ? (
          <StatusDisc state="done" size={15} />
        ) : tone === "needs" ? (
          <Icon name="triangle-alert" size={15} className="text-amber" />
        ) : (
          <StatusDisc state="fail" size={15} />
        )}
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-[6px]">
        <p className="leading-[19px]">{children}</p>
        {link !== undefined && <span className="text-ink">{link}</span>}
      </div>
      {action !== undefined && <span className="shrink-0">{action}</span>}
    </div>
  );
}

/** The ink-3 summary card under the wizard's step list: "Advisory project · Ridgeline …". */
export function WizardSummary({ children }: { children: ReactNode }): JSX.Element {
  return (
    <p className="rounded-nested bg-shell px-[12px] py-[9px] text-dense text-ink-3 inset-shadow-hair">
      {children}
    </p>
  );
}

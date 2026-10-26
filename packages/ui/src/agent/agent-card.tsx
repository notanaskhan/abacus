import type { JSX } from "react";
import { CatalogBadge, CatalogCard } from "../catalog/catalog-kit";
import { cn } from "../cn";
import { Button } from "../components/button";
import { Tag } from "../components/pill";
import { Icon, type IconName } from "../icons";

// C-11 AgentCard and IconTile (F-05-T59; C-11 Agent Card Library kit handoff §2 and §4): the card
// of a library agent on the T5 catalog grid. Only the 34px icon tile carries colour, and only a
// category tone; the card is white, 210 tall, with the name, three clamped lines of description,
// one category tag and its single action on the bottom edge: "Details…", or "Notify me" on a
// coming-soon card. The description is catalog copy published with the agent, not agent output.

/** The seven tones of C-11 §4: a token fill and a Lucide glyph per category. */
export const AGENT_TONES = {
  review: { fill: "bg-green", icon: "file-search" },
  preparation: { fill: "bg-espresso", icon: "panels-top-left" },
  audit: { fill: "bg-espresso", icon: "file-text" },
  research: { fill: "bg-amber", icon: "notebook-text" },
  client: { fill: "bg-clay", icon: "message-circle" },
  operations: { fill: "bg-red", icon: "sliders-horizontal" },
  close: { fill: "bg-green", icon: "landmark" },
} as const satisfies Record<string, { fill: string; icon: IconName }>;

export type AgentTone = keyof typeof AGENT_TONES;

/** The 34 tile, radius 8, a white 17px glyph on the tone's fill with the lift shadow. */
export function IconTile({
  tone,
  size = 34,
  className,
}: {
  tone: AgentTone;
  size?: 34 | 44;
  className?: string;
}): JSX.Element {
  const t = AGENT_TONES[tone];
  return (
    <span
      aria-hidden="true"
      data-icon-tile={tone}
      className={cn(
        "flex flex-none items-center justify-center text-on-dark shadow-lift",
        size === 34 ? "size-[34px] rounded-tile" : "size-[44px] rounded-menu-inner",
        t.fill,
        className,
      )}
    >
      <Icon name={t.icon} size={size === 34 ? 17 : 21} />
    </span>
  );
}

/** An agent's state in the library: the registry's `agent_template` codes the card draws. */
export type AgentCardStatus = "available" | "installed" | "coming_soon";

export interface AgentCardProps {
  name: string;
  description: string;
  /** The one tag: the category's label ("Tax Review"). */
  category: string;
  tone: AgentTone;
  status: AgentCardStatus;
  /** A coming-soon card the viewer asked to hear about. */
  notifying?: boolean;
  onDetails?: () => void;
  onNotify?: () => void;
}

const STATUS_WORD: Record<AgentCardStatus, string> = {
  available: "Available",
  installed: "Installed",
  coming_soon: "Coming soon",
};

export function AgentCard({
  name,
  description,
  category,
  tone,
  status,
  notifying = false,
  onDetails,
  onNotify,
}: AgentCardProps): JSX.Element {
  const soon = status === "coming_soon";
  return (
    <CatalogCard label={`${name}, ${STATUS_WORD[status]}`} height={210} still={soon}>
      <div data-agent-card={status} className="flex items-start justify-between gap-[8px]">
        <IconTile tone={tone} />
        <CatalogBadge state={{ object: "agent_template", code: status }} />
      </div>
      <p title={name} className="mt-[10px] truncate text-tab font-medium tracking-[-0.012em]">
        {name}
      </p>
      <p className="mt-[6px] line-clamp-3 text-cell text-ink-2">{description}</p>
      <Tag className="mt-[8px] self-start">{category}</Tag>
      <div className="mt-auto pt-[8px]">
        {soon ? (
          <Button
            variant="secondary"
            size="md"
            aria-pressed={notifying}
            {...(notifying ? { icon: "check" as const } : {})}
            {...(onNotify === undefined ? {} : { onClick: onNotify })}
          >
            {notifying ? "Notifying you" : "Notify me"}
          </Button>
        ) : (
          <Button
            variant="secondary"
            size="md"
            opensDialog
            aria-haspopup="dialog"
            aria-label={`Details for ${name}`}
            {...(onDetails === undefined ? {} : { onClick: onDetails })}
          >
            Details…
          </Button>
        )}
      </div>
    </CatalogCard>
  );
}

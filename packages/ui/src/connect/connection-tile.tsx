import type { JSX } from "react";
import { CatalogBadge, CatalogCard } from "../catalog/catalog-kit";
import { Button } from "../components/button";
import { VendorTile, type VendorTone } from "../icons";

// C-14 ConnectionTile (F-05-T59; C-14 Connect kit handoff §2, T5e and TPL-05e): one integration on
// the T5 catalog grid, 212 tall. The tile at the top left is the vendor's monogram on the category
// colour of its first category (F-05-T13's VendorTile): never a vendor logo and never a brand
// colour. Then the badge, the name, three clamped lines, the category labels joined by " · ", the
// scope line and the actions for the state.

/** The tile states the T5 frames draw; the registry's `integration` codes. */
export type ConnectionStatus = "available" | "connected" | "connecting" | "coming_soon";

export interface ConnectionTileProps {
  /** The vendor's name as text: the only place the vendor appears. */
  name: string;
  description: string;
  /** The category labels, first one first: "Productivity · Communications · …". */
  categories: readonly string[];
  /** The first category's colour. */
  tone: VendorTone;
  status: ConnectionStatus;
  /** "Firm connection · added by Felix Andersen", "Personal connection · acts as you". */
  scope: string;
  notifying?: boolean;
  onEnable?: () => void;
  onDetails?: () => void;
  onDisconnect?: () => void;
  onNotify?: () => void;
}

const STATUS_WORD: Record<ConnectionStatus, string> = {
  available: "Available",
  connected: "Connected",
  connecting: "Connecting…",
  coming_soon: "Coming soon",
};

const on = (fn: (() => void) | undefined): { onClick?: () => void } =>
  fn === undefined ? {} : { onClick: fn };

export function ConnectionTile({
  name,
  description,
  categories,
  tone,
  status,
  scope,
  notifying = false,
  onEnable,
  onDetails,
  onDisconnect,
  onNotify,
}: ConnectionTileProps): JSX.Element {
  const details = (disabled = false): JSX.Element => (
    <Button
      variant="secondary"
      size="md"
      opensDialog
      aria-haspopup="dialog"
      aria-label={`Details for ${name}`}
      disabled={disabled}
      {...on(onDetails)}
    >
      Details…
    </Button>
  );
  return (
    <CatalogCard
      label={`${name}, ${STATUS_WORD[status]}`}
      height={212}
      still={status === "coming_soon"}
    >
      <div data-connection-tile={status} className="flex items-start justify-between gap-[8px]">
        <VendorTile name={name} tone={tone} />
        <CatalogBadge state={{ object: "integration", code: status }} />
      </div>
      <p title={name} className="mt-[10px] truncate text-tab font-medium tracking-[-0.012em]">
        {name}
      </p>
      <p className="mt-[6px] line-clamp-3 text-cell text-ink-2">{description}</p>
      <p data-tags="" className="mt-[8px] truncate text-meta font-medium text-ink-2">
        {categories.join(" · ")}
      </p>
      <p data-scope="" className="mt-[4px] truncate text-meta text-ink-3">
        {scope}
      </p>
      <div className="mt-auto flex gap-[6px] pt-[10px]">
        {status === "available" && (
          <>
            <Button variant="primary" size="md" {...on(onEnable)}>
              Enable
            </Button>
            {details()}
          </>
        )}
        {status === "connected" && (
          <>
            {details()}
            <Button variant="destructive" size="md" {...on(onDisconnect)}>
              Disconnect
            </Button>
          </>
        )}
        {status === "connecting" && details(true)}
        {status === "coming_soon" && (
          <Button
            variant="secondary"
            size="md"
            aria-pressed={notifying}
            {...(notifying ? { icon: "check" as const } : {})}
            {...on(onNotify)}
          >
            {notifying ? "Notifying you" : "Notify me"}
          </Button>
        )}
      </div>
    </CatalogCard>
  );
}

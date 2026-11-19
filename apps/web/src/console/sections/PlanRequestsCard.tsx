// Plan requests (G-04-T17; G-04 §5.1 PLT-01b "Plan requests card (undesigned)"; DEC-32, DEC-5701):
// the console tile counting requests sent to Accrued, and the card in the tenant drawer listing a
// tenant's requests (seats, agent minutes, modules) with who approved each at the firm and "Mark
// applied" once billing has applied it. Nothing here changes the plan by itself.
import type { PlatformPlanRequestOut, PlatformPlanRequestsOut } from "@abacus/api-client";
import { Button, EmptyState, Pill, StatusTile } from "@abacus/ui";
import type { JSX } from "react";
import { SECTIONS_COPY } from "./copy";

const C = SECTIONS_COPY.planRequests;

export function PlanRequestsTile({
  data,
  onSelect,
  selected = false,
}: {
  data: PlatformPlanRequestsOut;
  onSelect?: () => void;
  selected?: boolean;
}): JSX.Element {
  return (
    <StatusTile
      count={data.counts.sent_to_accrued ?? 0}
      label={C.tile}
      variant="amber"
      selected={selected}
      {...(onSelect === undefined ? {} : { onSelect })}
    />
  );
}

function Row({
  r,
  onMarkApplied,
}: {
  r: PlatformPlanRequestOut;
  onMarkApplied?: ((r: PlatformPlanRequestOut) => void) | undefined;
}): JSX.Element {
  const what =
    r.kind === "modules" ? r.modules_add.join(", ") : C.change(r.from_value, r.to_value);
  return (
    <li className="flex items-center gap-[8px] py-[8px] text-[13px] hairline-t first:border-t-0">
      <span className="flex flex-1 flex-col">
        <span className="text-ink">
          {C.kind[r.kind]} · {what}
        </span>
        <span className="text-[12px] text-ink-3">{C.approvedBy(r.approved_by_display_name)}</span>
      </span>
      {r.status === "applied" ? (
        <Pill variant="green-tint" size="sm" check>
          {C.applied}
        </Pill>
      ) : (
        <Button size="sm" variant="secondary" onClick={() => onMarkApplied?.(r)}>
          {C.markApplied}
        </Button>
      )}
    </li>
  );
}

export function PlanRequestsCard({
  tenantCode,
  data,
  onMarkApplied,
}: {
  tenantCode: string;
  data: PlatformPlanRequestsOut;
  onMarkApplied?: (r: PlatformPlanRequestOut) => void;
}): JSX.Element {
  const mine = data.items.filter((r) => r.tenant_code === tenantCode);
  return (
    <section
      aria-label={C.card}
      data-console-section="plan-requests"
      className="flex flex-col gap-[6px] bg-card p-[12px] hairline"
    >
      <h3 className="text-[13.5px] font-medium text-ink">{C.card}</h3>
      {mine.length === 0 ? (
        <EmptyState title={C.empty} />
      ) : (
        <ul className="flex flex-col">
          {mine.map((r) => (
            <Row key={r.id} r={r} onMarkApplied={onMarkApplied} />
          ))}
        </ul>
      )}
    </section>
  );
}

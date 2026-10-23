import { EmptyState, Pane, PortalLayout } from "@abacus/ui";
import { type JSX, useState } from "react";
import { PLANNED_VISIBLE } from "../app-core/planned";
import { usePortalToolbar } from "../domain/portal";
import { EntitySwitcher } from "./EntitySwitcher";

// The portal's signed-in frame (P-08-T07): T7 `PortalLayout` with the PortalToolbar drawn from
// `/v1/me` → `portal` (the nav the server unions from the person's grants, Approvals only for an
// entity scope) and the EntitySwitcher at the head of the rail. The areas themselves are later
// tasks (POR-02 P-08-T15, POR-03 R-01): until then an area is a planned target, drawn as "Not
// built yet" in fixture builds and empty in production, where no landing can reach it yet.

const NOT_BUILT = "Not built yet";

export function PortalShell({
  area,
  onNavigate,
}: {
  area: string;
  onNavigate?: (label: string) => void;
}): JSX.Element | null {
  const [scopeId, setScopeId] = useState<string | null>(null);
  const bar = usePortalToolbar(scopeId);
  if (bar === undefined) return null;
  return (
    <PortalLayout
      variant="split"
      user={bar.user}
      nav={bar.nav}
      active={area}
      {...(onNavigate === undefined ? {} : { onNavigate })}
      rail={
        <Pane header={false}>
          <EntitySwitcher scopes={bar.scopes} value={bar.scope?.id} onChange={setScopeId} />
        </Pane>
      }
    >
      <Pane header={false}>{PLANNED_VISIBLE && <EmptyState title={NOT_BUILT} />}</Pane>
    </PortalLayout>
  );
}

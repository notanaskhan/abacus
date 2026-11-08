import { EmptyState } from "@abacus/ui";
import type { JSX } from "react";
import { PLANNED_VISIBLE } from "../../app-core/planned";

// POR-08 Approvals (R-02-T06): the lazy route stub at `/approvals`, planned behind the server's
// nav (entity scopes only). Fixture builds draw "Not built yet"; production draws nothing, as for
// every planned portal area. R-02-T15 builds the screen in this chunk.
export function POR08(): JSX.Element | null {
  return PLANNED_VISIBLE ? <EmptyState title="Not built yet" /> : null;
}

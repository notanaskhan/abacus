import { EmptyState } from "@abacus/ui";
import type { JSX } from "react";
import { PLANNED_VISIBLE } from "../../app-core/planned";

// POR-15 Governance room (R-02-T06): the lazy route stub at `/governance` and
// `/governance/$communicationId`, on the reduced shell (`governanceNav`). Fixture builds draw
// "Not built yet"; production draws nothing. R-02-T17 builds the screen in this chunk.
export function POR15(): JSX.Element | null {
  return PLANNED_VISIBLE ? <EmptyState title="Not built yet" /> : null;
}

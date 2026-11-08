import { EmptyState } from "@abacus/ui";
import type { JSX } from "react";
import { PLANNED_VISIBLE } from "../../app-core/planned";

// POR-09 Deliverables (R-02-T06): the lazy route stub at `/deliverables` (with `?section=k1s`,
// the target of T-02's DV-11 banner) and `/deliverables/$deliverableId`. Fixture builds draw "Not
// built yet"; production draws nothing. R-02-T16 builds the screen in this chunk.
export function POR09(): JSX.Element | null {
  return PLANNED_VISIBLE ? <EmptyState title="Not built yet" /> : null;
}

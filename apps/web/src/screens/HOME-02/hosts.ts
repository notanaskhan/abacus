// Where HOME-02's "Open" goes (I-01-T16): the gate's `subject_route`, a screen code with its ids
// (docs/contracts/home-and-gates.md, I-01-T13), resolved through the manifest's builders as
// HOME-01's rows are, plus the hosts this queue opens that HOME-01 does not: a return's final
// approval opens TAX-02 ("TAX-02?returnId=…"). Opaque ids only (ADR-031); a row is a link, never a
// decision control (INV-1).
import type { HumanGateOut } from "@abacus/api-client";
import { hrefOf, to } from "../../routes/to";
import { type HostRoutes, resolveRoute } from "../HOME-01/hosts";

const ROUTES: HostRoutes = {
  "AUD-03": {
    ids: ["auditId"],
    search: ["item"],
    build: (p) => to.AUD03({ auditId: p.auditId ?? "" }),
  },
  "BND-02": {
    ids: ["binderId"],
    search: ["request"],
    build: (p) => to.BND02({ binderId: p.binderId ?? "" }),
  },
  "TAX-02": {
    ids: ["returnId"],
    search: [],
    build: (p) => to.TAX02({ returnId: p.returnId ?? "" }),
  },
};

/** The gate's host as an href, or undefined while it names nothing routed. */
export function openHref(gate: HumanGateOut): string | undefined {
  return gate.subject_route == null ? undefined : resolveRoute(gate.subject_route, ROUTES);
}

/** HOME-01, the Home segmented's "My work". */
export const MY_WORK = hrefOf(to.HOME01());

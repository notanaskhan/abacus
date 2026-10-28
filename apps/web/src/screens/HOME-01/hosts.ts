// Where a Waiting-on-you row opens while `home.approvals` is off (I-01-T13; I-01 AC2.4, DV-3):
// the host screen where its gate is decided, until HOME-02 takes over (I-01-T21).
//
// - A row whose owner gave it a `subject_route` opens that: a screen code with its ids
//   ("AUD-03?auditId=…&item=…", "BND-02?binderId=…&request=…"; docs/contracts/home-and-gates.md
//   §6), resolved through the manifest's builders so only routed screens are ever linked.
// - Otherwise the gate's own ids decide: acceptance opens CLI-07, the independence conclusion,
//   confirmation and EQR eligibility open CLI-08.
// - Anything else (agent outputs, sends) has no built host yet and stays plain text.
//
// Opaque ids only, never names (ADR-031). Nothing here decides a gate (INV-1): a row is a link.
import type { HumanGateOut } from "@abacus/api-client";
import { to } from "../../routes/to";

type Target = { readonly to: string; readonly params?: Readonly<Record<string, string>> };

function pathOf(target: Target): string {
  const params = target.params ?? {};
  return target.to.replace(/\$(\w+)/gu, (_m, name: string) =>
    encodeURIComponent(params[name] ?? ""),
  );
}

function withSearch(path: string, search: Readonly<Record<string, string>>): string {
  const query = new URLSearchParams(search).toString();
  return query === "" ? path : `${path}?${query}`;
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/iu;

/** The screens a `subject_route` may name, the path ids each needs and the search it may carry. */
const ROUTES: Readonly<
  Record<
    string,
    {
      ids: readonly string[];
      search: readonly string[];
      build: (p: Record<string, string>) => Target;
    }
  >
> = {
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
};

/** A `subject_route` read as a link, or undefined when it names a screen or id it may not. */
export function routeOf(code: string): string | undefined {
  const [screen = "", query = ""] = code.split("?", 2);
  const route = ROUTES[screen];
  if (route === undefined) return undefined;
  const given = new URLSearchParams(query);
  const ids: Record<string, string> = {};
  for (const name of route.ids) {
    const value = given.get(name);
    if (value === null || !UUID.test(value)) return undefined;
    ids[name] = value;
  }
  const search: Record<string, string> = {};
  for (const name of route.search) {
    const value = given.get(name);
    if (value !== null && UUID.test(value)) search[name] = value;
  }
  return withSearch(pathOf(route.build(ids)), search);
}

const CLI08_SUBKINDS: ReadonlySet<string> = new Set([
  "independence_conclusion_due",
  "independence_confirmation_due",
  "eqr_eligibility_due",
]);

/** Where the row opens: its host gate, or undefined while that host is not built. */
export function hostHref(gate: HumanGateOut): string | undefined {
  if (gate.subject_route != null) return routeOf(gate.subject_route);
  if (gate.client_id === null || gate.engagement_id === null) return undefined;
  const ids = { clientId: gate.client_id, engagementId: gate.engagement_id };
  if (gate.subkind === "acceptance_decision_due") return pathOf(to.CLI07(ids));
  if (CLI08_SUBKINDS.has(gate.subkind)) return pathOf(to.CLI08(ids));
  return undefined;
}

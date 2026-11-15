// WB-10 Workbench › Connect (a–i) and WB-11 integration detail (a–f) on fixtures (W-01-T03; A-01 §5.4;
// docs/screens/WB-10.md, WB-11.md). Felix Andersen (IT/Security) unless stated; E0 Mon Sep 14,
// 2026 9:24 AM CT, the Aug 17 9:05 AM replay for f and c, E2 Thu Oct 1 for h and i. Every
// scenario answers the C20 v2 stub routes from `seed/connect.ts`, whose counts are computed.
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import { AUG17, type ConnectView, E0, E2, cchDetail, connectCatalog } from "../seed/connect";

const BASE = seedScenario();

function scenario(
  state: string,
  persona: string,
  clock: string,
  handlers: Record<string, FixtureHandler>,
): Scenario {
  return {
    state,
    persona,
    clock,
    get handlers() {
      return { ...BASE.handlers, ...handlers };
    },
  };
}

function wb10(state: string, view: ConnectView, persona = "felix-andersen"): Scenario {
  return scenario(state, persona, view.at ?? E0, {
    "GET /v1/integrations/catalog": ({ query }) => {
      const asked: ConnectView = { ...view };
      const category = query.get("category");
      const status = query.get("status");
      const q = query.get("q");
      if (category) asked.category = category as NonNullable<ConnectView["category"]>;
      if (status) asked.status = status as NonNullable<ConnectView["status"]>;
      if (q) asked.q = q;
      return json(connectCatalog(asked));
    },
    "GET /v1/integrations/{key}": ({ params }) =>
      params.key === "cch"
        ? json(cchDetail(view.at === AUG17 ? "c" : "a"))
        : json({ detail: "not_implemented" }, 501),
  });
}

export const wb10Scenarios = defineScenarios({
  a: wb10("a", {}),
  b: wb10("b", { category: "erp" }),
  c: wb10("c", { status: "connected" }),
  d: wb10("d", { viewer: "hannah-leclerc" }, "hannah-leclerc"),
  e: wb10("e", { overrides: { gws: "connecting" } }),
  f: wb10("f", { at: AUG17, overrides: { cch: "needs_reauth" } }),
  g: wb10("g", { q: "Karbon" }),
  h: wb10("h", { at: E2 }),
  i: wb10("i", { at: E2, category: "grc" }),
});

function wb11(
  state: string,
  persona: string,
  clock: string,
  detail: ReturnType<typeof cchDetail>,
): Scenario {
  return scenario(state, persona, clock, {
    "GET /v1/integrations/{key}": () => json(detail),
    "POST /v1/integrations/{key}/disconnect": () => json({ detail: "not_implemented" }, 501),
  });
}

export const wb11Scenarios = defineScenarios({
  a: wb11("a", "felix-andersen", E0, cchDetail("a")),
  b: wb11("b", "hannah-leclerc", E0, cchDetail("f")),
  c: wb11("c", "felix-andersen", AUG17, cchDetail("c")),
  d: wb11("d", "felix-andersen", E0, cchDetail("a")),
  e: wb11("e", "felix-andersen", E0, cchDetail("a")),
  f: wb11("f", "hannah-leclerc", E0, cchDetail("f")),
});

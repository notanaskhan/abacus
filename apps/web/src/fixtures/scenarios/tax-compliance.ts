// T-01's five screens: one scenario per artboard with the persona and clock T-01 §5.4 names
// (T-01-T09; docs/screens/{CLI-05,ADM-05,ADM-08,TAX-09,TAX-12}.md). Each screen's build task
// re-exports its own from src/screens/<ID>/scenarios.ts.
import { type Scenario, defineScenarios } from "../../app-core/fixture-mode";
import { taxComplianceHandlers } from "../handlers/tax-compliance";
import { seedScenario } from "../scenario";

const E0 = seedScenario();

const at = (state: string, persona: string, clock: string): Scenario => ({
  state,
  persona,
  clock,
  handlers: { ...E0.handlers, ...taxComplianceHandlers(state) },
});

const MON_924 = "2026-09-14T09:24:00-05:00";

export const cli05 = defineScenarios({
  a: at("a", "kevin-osei", MON_924),
  b: at("b", "kevin-osei", "2026-09-14T09:04:00-05:00"),
  c: at("c", "kevin-osei", MON_924),
  d: at("d", "kevin-osei", MON_924),
  e: at("e", "kevin-osei", MON_924),
  f: at("f", "kevin-osei", MON_924),
  g: at("g", "kevin-osei", MON_924),
});

export const adm05 = defineScenarios({
  a: at("a", "grace-holloway", MON_924),
  b: at("b", "grace-holloway", MON_924),
  c: at("c", "grace-holloway", MON_924),
  d: at("d", "grace-holloway", MON_924),
  e: at("e", "grace-holloway", MON_924), // T-01 §2: Grace views every artboard; "Harold Stein" is the label
  f: at("f", "grace-holloway", MON_924),
  g: at("g", "grace-holloway", MON_924),
  h: at("h", "grace-holloway", MON_924),
});

export const adm08 = defineScenarios({
  a: at("a", "felix-andersen", MON_924),
  b: at("b", "felix-andersen", MON_924),
  c: at("c", "felix-andersen", MON_924),
  d: at("d", "felix-andersen", MON_924),
  e: at("e", "felix-andersen", MON_924),
  f: at("f", "felix-andersen", MON_924),
  g: at("g", "felix-andersen", MON_924),
});

export const tax09 = defineScenarios({
  a: at("a", "samuel-ito", "2026-09-16T11:42:00-05:00"),
  a2: at("a2", "samuel-ito", "2026-09-16T11:20:00-05:00"),
  b: at("b", "samuel-ito", MON_924),
  c: at("c", "samuel-ito", "2026-09-14T09:31:00-05:00"),
  d: at("d", "samuel-ito", "2026-09-16T11:43:00-05:00"),
  d2: at("d2", "samuel-ito", "2026-09-16T11:20:00-05:00"),
  e: at("e", "samuel-ito", "2026-09-10T09:30:00-05:00"),
  // Non-artboard (T-01-T15): no export yet.
  not_yet_exported: at("not_yet_exported", "samuel-ito", "2026-09-16T11:20:00-05:00"),
});

export const tax12 = defineScenarios({
  a: at("a", "grace-holloway", "2026-09-17T09:30:00-05:00"),
  a2: at("a2", "grace-holloway", "2026-09-17T09:30:00-05:00"),
  b: at("b", "grace-holloway", MON_924),
  c: at("c", "grace-holloway", "2026-09-17T18:12:00-05:00"),
  c2: at("c2", "daniel-reyes", "2026-09-18T11:06:00-05:00"),
  d: at("d", "grace-holloway", "2026-09-19T09:12:00-05:00"),
  e: at("e", "grace-holloway", "2026-09-17T09:30:00-05:00"),
});

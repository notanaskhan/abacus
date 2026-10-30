// ADM-05 a–h (T-01-T09 scenarios; built by T-01-T13 and T22): one scenario per artboard. OPENS is
// the search each state opens with; g's selection is made by the test (rows 3 to 5).
import { scenarios } from "../../fixtures/scenarios/ADM-05";

export { scenarios };

export type Adm05State = keyof typeof scenarios;

export const OPENS: Readonly<Record<Adm05State, string>> = {
  a: "",
  b: "?status=expiring",
  c: "",
  d: "",
  e: "?q=harold",
  f: "?purpose=offshore_disclosure",
  g: "",
  h: "",
};

export const STATES = Object.keys(scenarios) as Adm05State[];

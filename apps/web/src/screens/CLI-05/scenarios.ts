// CLI-05 a–g (T-01-T09 scenarios; T-01-T14 builds d and f, T-01-T34 b, c, e and g): one scenario
// per artboard, the taxpayer entity it opens on and the section it opens at.
import { ENTITY, SECTION, scenarios } from "../../fixtures/scenarios/CLI-05";

export { ENTITY, SECTION, scenarios };

export type Cli05State = keyof typeof scenarios;

export const STATES = Object.keys(scenarios) as Cli05State[];

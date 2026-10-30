// CLI-05 a–g (T-01-T09 scenarios; T-01-T14 builds d and f): one scenario per artboard and the
// taxpayer entity it opens on.
import { ENTITY, scenarios } from "../../fixtures/scenarios/CLI-05";

export { ENTITY, scenarios };

export type Cli05State = keyof typeof scenarios;

export const STATES = Object.keys(scenarios) as Cli05State[];

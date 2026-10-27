// POR-20 a–l (R-01-T25): one scenario per artboard; the data and handlers live under
// fixtures/scenarios/POR-20.ts. OPENS is the template, width and sample each state opens with.
import { OPENS, SAMPLES, scenarios } from "../../fixtures/scenarios/POR-20";

export { OPENS, SAMPLES, scenarios };

export type Por20State = keyof typeof scenarios;

export const STATES = Object.keys(scenarios) as Por20State[];

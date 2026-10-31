// POR-05 a–f (T-02-T08 scenarios; built by T-02-T24): one scenario per artboard.
import { scenarios } from "../../fixtures/scenarios/POR-05";

export { scenarios };

export type Por05State = keyof typeof scenarios;

export const STATES = Object.keys(scenarios) as Por05State[];

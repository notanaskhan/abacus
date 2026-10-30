// TAX-09 a–e (T-01-T09 scenarios; built by T-01-T15), plus the non-artboard "Not yet exported".
// Every artboard opens with the popover shown; e opens on the import diff.
import { scenarios } from "../../fixtures/scenarios/TAX-09";

export { scenarios };

export type Tax09State = keyof typeof scenarios;

export const STATES = Object.keys(scenarios) as Tax09State[];

// INB-02's artboards (N-01-T15): the scenario per artboard and the message its sheet opens.
export { messageOf, scenarios } from "../../fixtures/scenarios/INB-02";
export const STATES = ["a", "a2", "b", "c", "d", "e", "f", "g"] as const;
export type Inb02State = (typeof STATES)[number];

// POR-13 · My K-1s a–f (T-02-T27): T-02-T08's personas and clocks (tax-returns.ts), each answering
// the portal K-1 reads for its artboard (seed/portal-k1s.ts). d opens the taxpayer-ID sheet.
export { por13 as scenarios } from "./tax-returns";

export type Por13State = "a" | "b" | "c" | "d" | "e" | "f";

/** What an artboard opens with: d holds the Update taxpayer ID sheet open. */
export const OPENING: Readonly<Partial<Record<Por13State, "tin">>> = { d: "tin" };

import { amount } from "@abacus/ui";

/** A TAX-13 cell's figure: the handoff's grammar carries no dollar sign (DV-TAX-13-4). */
export const figure = (v: string | null | undefined): string =>
  v === null || v === undefined ? "—" : amount(v, "whole").text.replace("$", "");

// F-08-T28: figures on paper. Negatives in parentheses and never red; "$" only where the row says.
import { amount } from "../format";

export function paperAmount(value: number | null, dollar = false): string {
  if (value === null) return "";
  const { text } = amount(String(value), "whole");
  return dollar ? `$ ${text}` : text;
}

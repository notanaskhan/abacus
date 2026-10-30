// CLI-05's scenarios (T-01-T09, built by T-01-T14): T-01's five screens share one module; the
// entity each artboard opens on is the screen contract's (Whitley a–d, Ferris f).
import { FERRIS_ENTITY, WHITLEY_ENTITY } from "../seed/tax-profile";

export { cli05 as scenarios } from "./tax-compliance";

export const ENTITY = {
  a: WHITLEY_ENTITY,
  b: WHITLEY_ENTITY,
  c: WHITLEY_ENTITY,
  d: WHITLEY_ENTITY,
  e: WHITLEY_ENTITY,
  f: FERRIS_ENTITY,
  g: WHITLEY_ENTITY,
} as const;

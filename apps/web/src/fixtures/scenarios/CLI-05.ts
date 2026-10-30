// CLI-05's scenarios (T-01-T09, built by T-01-T14): T-01's five screens share one module; the
// entity each artboard opens on is the screen contract's (Whitley a–d, Ridgeline e, Ferris f,
// Santos g), and the section it opens at (T-01-T34).
import {
  FERRIS_ENTITY,
  RIDGELINE_ENTITY,
  SANTOS_ENTITY,
  WHITLEY_ENTITY,
} from "../seed/tax-profile";

export { cli05 as scenarios } from "./tax-compliance";

export const ENTITY = {
  a: WHITLEY_ENTITY,
  b: WHITLEY_ENTITY,
  c: WHITLEY_ENTITY,
  d: WHITLEY_ENTITY,
  e: RIDGELINE_ENTITY,
  f: FERRIS_ENTITY,
  g: SANTOS_ENTITY,
} as const;

export const SECTION = {
  a: "transcripts",
  b: "transcripts",
  c: "authorizations",
  d: "consents",
  e: "elections",
  f: "consents",
  g: "authorizations",
} as const;

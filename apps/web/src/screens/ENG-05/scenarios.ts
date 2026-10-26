// ENG-05 a–e (P-07-T39): one scenario per artboard. The data and handlers live under
// fixtures/scenarios/ENG-05.ts; each also names the engagement it opens and the overlay it opens on.
export {
  type Eng05State,
  KIRA,
  OPENS,
  OVERLAYS,
  THOMAS,
  freshScenario,
  scenarios,
} from "../../fixtures/scenarios/ENG-05";
import { type Eng05State, scenarios } from "../../fixtures/scenarios/ENG-05";

export const STATES = Object.keys(scenarios) as Eng05State[];

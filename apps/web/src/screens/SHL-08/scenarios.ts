// SHL-08 a–f, h (P-03-T07): one scenario per artboard P-03 builds (g, Annotate, is K-03's). The
// data and handlers live under fixtures/scenarios/SHL-08.ts; OPENS names the version, match and
// stack each artboard opens with; the EvidenceViewer is P-03-T14.
export {
  NORTHWIND_TB_ROWS,
  OPENS,
  type Shl08TbRow,
  type Shl08Opens,
  type Shl08State,
  scenarios,
} from "../../fixtures/scenarios/SHL-08";
import { type Shl08State, scenarios } from "../../fixtures/scenarios/SHL-08";

export const STATES = Object.keys(scenarios) as Shl08State[];

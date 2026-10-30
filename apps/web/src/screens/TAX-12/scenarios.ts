// TAX-12 a–e (T-01-T09 scenarios); T-01-T24 builds a, a2 and b, the rest with T-01-T35 to T40.
import { scenarios } from "../../fixtures/scenarios/TAX-12";

export { scenarios };

export type Tax12State = keyof typeof scenarios;

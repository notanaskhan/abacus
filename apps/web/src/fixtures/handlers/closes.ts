// C-01-T12: the close shell in fixture mode, typed against the closes stubs (C-01-T04, T05).
// `GET /v1/closes/{close_id}` answers Copperleaf August for every close id (the shell's record
// bar and Review count); the screens' own reads stay 501 here until their rows add scenarios
// from the figure book (C-01-T13).
import { type FixtureHandler, json } from "../../app-core/fixture-mode";
import { copperleafAugust } from "../seed/closes";

const notYet = () => json({ detail: "not_implemented" }, 501);

export function closeHandlers(): Record<string, FixtureHandler> {
  return {
    "GET /v1/closes/{close_id}": () => json(copperleafAugust()),
    "GET /v1/closes/{close_id}/runs": notYet,
    "GET /v1/closes/{close_id}/requests": notYet,
    "GET /v1/closes/{close_id}/accounts": notYet,
    "GET /v1/closes/{close_id}/issues": notYet,
    "GET /v1/closes/{close_id}/flux": notYet,
  };
}

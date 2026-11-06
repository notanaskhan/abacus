// NOT-01 every artboard (N-04-T26) in fixture mode.
import { walkBoards } from "./fixture-boards";

walkBoards("NOT-01", "/notices", [
  { st: "a", ready: "Marcus & Dana Whitley" },
  { st: "b", ready: "Aurelio Santos" },
  { st: "c", ready: "Aurelio Santos" },
  { st: "d", ready: "Aurelio Santos" },
  { st: "duplicate", ready: "Notices" },
  { st: "manual", ready: "Notices" },
  { st: "e", ready: "Notices" },
  { st: "f", ready: "Notices" },
  { st: "g", ready: "Notices" },
]);

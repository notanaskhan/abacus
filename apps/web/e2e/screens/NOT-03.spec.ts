// NOT-03 a to g and d2 (N-04-T26) in fixture mode, under NOT-02's Response tab.
import { walkBoards } from "./fixture-boards";

const READY = "Response";
walkBoards("NOT-03", "/notices/_noticeId_", [
  { st: "a", ready: READY },
  { st: "b", ready: READY },
  { st: "c", ready: READY },
  { st: "d", ready: READY },
  { st: "d2", ready: READY },
  { st: "e", ready: READY },
  { st: "f", ready: READY },
  { st: "g", ready: READY },
]);

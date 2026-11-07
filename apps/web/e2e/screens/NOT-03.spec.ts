// NOT-03 a to g and d2 (N-04-T26) in fixture mode, under NOT-02's Response tab.
import { walkBoards } from "./fixture-boards";

const READY = "Response";
walkBoards(
  "NOT-03",
  "/notices/_noticeId_",
  [
    { st: "a", ready: READY, search: "tab=response" },
    { st: "b", ready: READY, search: "tab=response" },
    { st: "c", ready: READY, search: "tab=response" },
    { st: "d", ready: READY, search: "tab=response" },
    { st: "d2", ready: READY, search: "tab=response" },
    { st: "e", ready: READY, search: "tab=response" },
    { st: "f", ready: READY, search: "tab=response" },
    { st: "g", ready: READY, search: "tab=response" },
  ],
  ["notices.workspace"],
);

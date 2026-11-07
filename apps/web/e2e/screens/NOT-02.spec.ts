// NOT-02 a to f and a2 (N-04-T26) in fixture mode.
import { walkBoards } from "./fixture-boards";

walkBoards("NOT-02", "/notices/_noticeId_", [
  { st: "a", ready: "753.01" },
  { st: "b", ready: "Comparing 6 information returns" },
  { st: "c", ready: "decided by Daniel Reyes" },
  { st: "d", ready: "Front Range Bank" },
  { st: "a2", ready: "Decision requested", search: "tab=activity" },
  { st: "e", ready: "so the gain is zero" },
  { st: "f", ready: "Form 2848 to send" },
]);

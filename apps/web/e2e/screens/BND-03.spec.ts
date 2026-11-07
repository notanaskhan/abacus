// BND-03 a to e and flag off (T-03-T17) in fixture mode.
import { walkBoards } from "./fixture-boards";

walkBoards(
  "BND-03",
  "/binders/questionnaires/_questionnaireId_",
  [
    { st: "a", ready: "Questionnaire" },
    { st: "b", ready: "Questionnaire" },
    { st: "c", ready: "Questionnaire" },
    { st: "d", ready: "Questionnaire" },
    { st: "e", ready: "Questionnaire" },
  ],
  ["binders.engine"],
);

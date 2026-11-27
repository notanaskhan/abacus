// SHT-02's words, verbatim from the handoff (screens/SHT-02 spec.md) where it words them.
type Usage = {
  views: number;
  viewNames: readonly string[];
  rules: number;
  agentColumns: readonly string[];
};

const plural = (n: number, one: string, many: string): string =>
  `${String(n)} ${n === 1 ? one : many}`;

export const COPY = {
  addTitle: "Add column",
  editTitle: (label: string) => `Edit column · ${label}`,
  sections: { column: "Column", type: "Type", rules: "Rules", data: "Data" },
  keys: {
    name: "Name",
    description: "Description",
    position: "Position",
    type: "Type",
    range: "Range",
    display: "Display",
    required: "Required",
    defaultValue: "Default",
    validation: "Validation",
    visible: "Visible to client",
    classification: "Classification",
    usedIn: "Used in",
  },
  after: (label: string) => `After ${label}`,
  rangeHint: "start – end",
  display: {
    month: "Month when the range is one month (Jun 2026)",
    date: "Date",
  },
  requiredHint: "before a preparer can sign off a row",
  defaultEmpty: "Empty",
  validation: { end_on_or_after_start: "End on or after start", none: "None" },
  visibleHelp:
    "Only request-facing sheets can show a column to the client. This is an internal workpaper.",
  requiredTag: "Required",
  classificationHelp:
    "Every field carries a classification. A column that holds client data starts as Restricted; the level sets export and retention rules.",
  reasonLabel: "Reason for a lower level",
  reasonHelp: "A level below Restricted on a column that holds client data needs a reason.",
  // The 11 types of §5.2, in order (K-03 SPEC-721).
  types: [
    { value: "text", label: "Text", hint: undefined },
    { value: "number", label: "Number", hint: undefined },
    { value: "currency", label: "Currency", hint: "dollars and cents" },
    { value: "date", label: "Date", hint: "single date or range" },
    { value: "single_select", label: "Single select", hint: "one of a list" },
    { value: "person", label: "Person", hint: "people on this engagement" },
    { value: "linked_evidence", label: "Linked evidence", hint: undefined },
    { value: "linked_request", label: "Linked request", hint: undefined },
    { value: "linked_risk", label: "Linked risk", hint: "from the risk register" },
    { value: "sign_off", label: "Sign-off", hint: "P and R slots" },
    {
      value: "agent",
      label: "Agent column",
      hint: "an agent proposes values · opens the agent-column editor",
    },
  ],
  // ADR-031's four levels, exactly.
  levels: [
    {
      value: "restricted",
      label: "Restricted",
      hint: "client financial data, evidence, ledger data, messages",
    },
    { value: "confidential", label: "Confidential", hint: "firm data and metadata" },
    { value: "internal", label: "Internal", hint: undefined },
    { value: "public", label: "Public", hint: undefined },
  ],
  usedIn: (u: Usage, column: string): string => {
    if (u.views === 0 && u.rules === 0 && u.agentColumns.length === 0) {
      return "0 saved views · 0 rules · 0 agent columns";
    }
    const parts: string[] = [];
    if (u.views > 0) {
      parts.push(
        `${plural(u.views, "saved view", "saved views")}${
          u.viewNames.length > 0 ? ` (${u.viewNames.join(" · ")})` : ""
        }`,
      );
    }
    if (u.rules > 0) parts.push(plural(u.rules, "rule", "rules"));
    if (u.agentColumns.length > 0) {
      parts.push(
        `${plural(u.agentColumns.length, "agent column", "agent columns")} (${u.agentColumns
          .map((a) => `${a} reads @${column}`)
          .join(", ")})`,
      );
    }
    return parts.join(" · ");
  },
  filled: (n: number) => `${plural(n, "row has", "rows have")} values`,
  note: "This adds the column to this engagement's sheet only. To change the firm template, edit BH-FS-430 in Knowledge › Engagement templates.",
  templateNote: "This changes the firm template. Engagements take it when they update to the new version.",
  typeWarning: (from: string, to: string, filled: number, u: Usage, column: string): string => {
    const clauses = [
      ...(u.views > 0
        ? [`${from} filters in ${plural(u.views, "saved view", "saved views")} stop working`]
        : []),
      ...u.agentColumns.map((a) => `${a} will read @${column} as ${to.toLowerCase()}`),
    ];
    const tail = clauses.length === 0 ? "" : ` ${clauses.join(", and ")}.`;
    return `Changing ${from} to ${to} keeps the ${String(filled)} values as ${to.toLowerCase()}.${tail}`;
  },
  keepType: (from: string) => `Keep ${from}`,
  changeType: "Change type",
  deleteColumn: "Delete column…",
  blockedTitle: (column: string) => `${column} can't be deleted`,
  blockedBody: (u: Usage, column: string): string => {
    const views =
      u.views > 0
        ? `${plural(u.views, "saved view", "saved views")} (${u.viewNames.join(", ")})`
        : "";
    const agents = u.agentColumns
      .map((a) => `the agent column ${a} refers to @${column}`)
      .join(", and ");
    const used =
      views !== "" && agents !== ""
        ? `It is used in ${views}, and ${agents}.`
        : views !== ""
          ? `It is used in ${views}.`
          : `${agents.charAt(0).toUpperCase()}${agents.slice(1)}.`;
    return `${used} Remove those references first. Deleting a column never removes evidence or sign-offs.`;
  },
  openAgent: (name: string) => `Open ${name}`,
  close: "Close",
  cancel: "Cancel",
  add: "Add column",
  save: "Save",
  readOnly: "Only managers can add or change columns.",
  suggest: (name: string) => `Suggest to ${name}…`,
  added: (label: string) => `${label} added · logged in Activity`,
  saved: (label: string) => `${label} saved · logged in Activity`,
  failed: "The column could not be saved.",
  loadFailed: "The sheet could not load.",
};

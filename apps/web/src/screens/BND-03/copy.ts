// BND-03 · Questionnaire editor (T-03-T09): verbatim from the handoff spec and docs/screens/BND-03.md.
// Counts and answers are the server's (QuestionnaireEditorOut); the copy frames them.

export const COPY = {
  tabs: { requests: "Requests", questions: "Questions", activity: "Activity" },
  tabsLabel: "Binder",
  rail: {
    title: "Questionnaire",
    template: "Template",
    templateValue: (name: string, v: number) => `${name} v${String(v)}`,
    answered: "Answered",
    answeredValue: (n: number, of: number, by: string | null, on: string | null) =>
      [`${String(n)} of ${String(of)}`, by, on === null ? null : `last answer ${on}`]
        .filter((p) => p !== null && p !== "")
        .join(" · "),
    sections: "Sections",
    logic: "Logic",
    followUps: (n: number) => `${String(n)} conditional follow-${n === 1 ? "up" : "ups"}`,
    reviewPoints: (n: number) => `${String(n)} review ${n === 1 ? "point" : "points"} raised`,
  },
  canvas: {
    title: "Questions",
    reorder: "Reorder",
    preview: "Preview as client",
    add: "+ Question",
    required: "Required",
    wording: "Client wording",
    answer: "Answer",
    unanswered: "—",
    notTriggered: "Not triggered",
    ifYes: (wording: string) => `If Yes → ${wording}`,
    reviewPoint: (title: string) => `Raised review point '${title}' · open in TAX-06`,
    makeRequired: (title: string) =>
      `Make required — this answer created the open request '${title}'`,
    empty: "No questions in this section.",
  },
  type: {
    yes_no: "Yes / No",
    amount: "Amount",
    choice: "Choice",
    date: "Date",
    text: "Text",
    upload_if_yes: "Upload if yes",
  } as Record<string, string>,
  // T-03-T10: the editing states b, c and d.
  editing: {
    edit: "Edit",
    done: "Done",
    wording: "Client wording",
    type: "Type",
    logic: (parent: string, equals: string) => `Show when ${parent.toUpperCase()} = ${equals}`,
    up: "Move up",
    down: "Move down",
    newQuestion: "New question",
    newWording: "Question for the client",
    save: "Save",
    discard: "Discard",
    unsaved: (n: number) => `${String(n)} unsaved ${n === 1 ? "change" : "changes"}`,
    stale: "Someone else changed this questionnaire. Reload to see their changes.",
    reload: "Reload",
  },
  dock: { title: "Client preview", desktop: "Desktop", phone: "Phone", label: "Preview size" },
  states: { notFound: "Questionnaire not found." },
} as const;

// WB-03 words (W-02-T21; handoff WB-03 spec.md, verbatim where it gives them).
export const COPY = {
  planTitle: "Plan",
  planReady: "Plan ready — approve?",
  dataItWillRead: "Data it will read",
  writesNeedApproval: "Writes that need your approval",
  approvePlan: "Approve plan",
  editPlan: "Edit plan…",
  cancelPlan: "Cancel",
  saveEdit: "Save",
  cancelEdit: "Cancel",
  stepLabel: (n: number) => `Step ${String(n)}`,
  cancelled: (who: string, when: string) => `Plan cancelled by ${who} · ${when}`,
  retryThose: (n: number) => `Retry those ${String(n)}`,
} as const;

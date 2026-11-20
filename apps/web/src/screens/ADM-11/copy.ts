// ADM-11 · Quality management dashboard (Q-05-T19): words verbatim from the handoff spec and the
// R2 revision.
import { count, date } from "@abacus/ui";

export const COPY = {
  title: "Quality management",
  sqms: "SQMS No. 1",
  year: "Evaluation year Dec 15, 2025 – Dec 15, 2026",
  office: "Office",
  allOffices: "All offices",
  tiles: {
    atRisk: "Objectives at risk",
    findings: "Open QM findings",
    override: "Agent override rate",
    accuracy: "Draft-vs-final accuracy",
    consultations: "Consultations open",
    evaluation: "Annual evaluation",
  },
  of: (n: number) => `of ${String(n)}`,
  findingsSub: (inspections: number, agents: number) =>
    `${String(inspections)} inspections · ${String(agents)} agent monitoring`,
  overrideSub: (o: number, n: number, tol: string) =>
    `${count(o)} of ${count(n)} · tolerance ${tol}% · `,
  insights: "Insights →",
  accuracySub: "145 filed TY2025 returns",
  days: (n: number) => `${String(n)} days`,
  due: "Due Dec 15, 2026",
  objectivesPane: "Objectives, risks & responses",
  columns: ["Component", "Objectives", "Risks", "Responses", "Health", "Owner"],
  onTrack: "On track",
  atRiskPill: "At risk",
  totalsAtRisk: (n: number) => `${String(n)} at risk`,
  firmWide: "Objectives are firm-wide.",
  processes: "Processes",
  riskProcess: "Firm's risk assessment process · last updated Jan 14, 2026",
  current: "Current",
  monitoring: "Monitoring & remediation · 6 inspections this cycle · 5 findings open",
  inProgress: "In progress",
  overridePane: "Agent override rate · 30 days",
  aiAdoption: "AI adoption",
  overrideHelp: "Override = a person changed or rejected the agent's output before adopting it.",
  total: "Total",
  unrated: (n: number) =>
    `${String(n)} other installed agents had fewer than 25 outputs and are not rated this period.`,
  sameAsInsights:
    "Same outputs and overrides as Insights › AI adoption. Learned-context items from these corrections are governed in WB-13.",
  openRuns: "Open run history",
  openFinding: (ref: string) => `Open finding ${ref}`,
  openLearned: "Open learned context",
  findingsPane: "Findings & consultations",
  agentMonitoring: "Agent monitoring",
  dueOn: (d: string) => `due ${d}`,
  consultationsBand: (n: number) => `Consultations · ${String(n)}`,
  components: {
    governance_leadership: "Governance & leadership",
    ethical_requirements: "Relevant ethical requirements",
    acceptance_continuance: "Acceptance & continuance",
    engagement_performance: "Engagement performance",
    resources: "Resources (human, technological, intellectual)",
    information_communication: "Information & communication",
  } as Readonly<Record<string, string>>,
  reasons: {
    census_misread: "Census column misread for rehired participants",
    loan_offset: "Loan offset classification",
    other: "Other",
  } as Readonly<Record<string, string>>,
  consultationSub: (at: string, ep: string | null | undefined) =>
    `opened ${date(at, { now: Date.parse(at) })} · EP ${ep ?? ""}`,
  emptyTitle: "No QM findings yet.",
  emptyBody: "Inspection findings and agent monitoring appear here.",
} as const;

// ADM-04 · AI policy & approval gates (G-02-T25; docs/screens/ADM-04.md "Copy"; handoff ADM-04
// spec.md, revision.md). Verbatim. The approver is Daniel Reyes, never the requester (DV-1).
export const COPY = {
  title: "AI policy",
  section: "ai-policy",
  chip: (n: number, on: string, by: string): string =>
    `BH AI policy v${String(n)} · published ${on} by ${by}`,
  awaiting: (name: string): string => `Awaiting approval · ${name}`,
  history: "Version history",
  discard: "Discard",
  saveAs: (n: number): string => `Save as v${String(n)}…`,
  unsaved: "Unsaved changes",
  readOnly: "Only partners can change the AI policy.",
  approve: (n: number): string => `Approve v${String(n)}`,
  gates: {
    title: "Approval gates",
    band: "Agents draft, test, propose and chase. People approve.",
    columns: [
      "Agent action",
      "Default human approver",
      "Policy acceptance",
      "Attest clients",
    ] as const,
    notAllowed: "Not allowed",
    policy: (ref: string): string => `Policy: ${ref}`,
    footer:
      "Defaults from 01 §2.4 and the IRS OPR AI guidance (Jun 24, 2026). Firms may only make them stricter.",
    popoverTitle: "Where this gate appears",
    popoverLog: (action: string): string => `Logged as ${action}`,
  },
  rows: {
    1: ["Classify and file a document", 'Staff or above ("Approve Document")'],
    2: [
      "Draft a return, workpaper or close task",
      "Preparer adopts it (L1) — Staff, Tax Preparer or above",
    ],
    3: ["Change a field after the draft (checkpoint)", "Preparer or reviewer"],
    4: ["Resolve an issue", "Assignee"],
    5: [
      "Proposed AJE within threshold",
      'Named human, one batch ("Approved by RM under BH AJE thresholds v2")',
    ],
    6: ["Proposed AJE above threshold", "Manager or partner"],
    7: ["Post an approved batch to the GL", "Senior with an approved batch"],
    8: ["Export a return to the tax engine", "Reviewer, after final approval (BH-TAX-02)"],
    9: [
      "Send a client message or reminder",
      "Staff or Firm Admin; template reminders on the ADM-10 cadence",
    ],
    10: ["Send a notice response", "Manager or partner"],
    11: [
      "Materiality, significant risks, deficiency severity, opinion",
      "Engagement partner (decision card)",
    ],
    12: [
      "Propose a change to a firm-made agent's instructions",
      "Methodology owner (Margaret Okonkwo) publishes; the scheduling user owns its schedule",
    ],
  } as Readonly<Record<number, readonly [string, string]>>,
  attest: {
    never: "Never",
    never_held_for_client: "Never — held for client approval",
    posting_disabled: "Posting disabled (ADM-08)",
    none: "—",
  },
  principal: {
    title: "Policy principal",
    off: "Off",
    on: "On · non-attest only",
    allow: "Allow published threshold policies to accept items",
    aje: "Policy: BH AJE thresholds v2 — payroll accruals ≤ $15,000; other accruals, prepaids, depreciation, deferred revenue ≤ $10,000",
    doc: "Policy: BH document confidence v1 — classification confidence ≥ 98%",
    help: "A policy principal is a firm-owned rule, not the agent. When on, items inside a published, versioned threshold are accepted and logged as 'Policy: BH AJE thresholds v2'. It never applies to attest clients, never shows as Accrued Agent, and any acceptance can be reversed by a person with the right role. Turning it on or off is recorded in the audit log.",
    requires: "Requires",
    requiresValue: "Partner approval + IT/Security acknowledgement",
    confirmTitle: "Allow policy acceptance?",
    confirmBody:
      "Items inside BH AJE thresholds v2 for non-attest clients will be accepted and logged as 'Policy: BH AJE thresholds v2'. People can reverse any acceptance.",
    confirmCheck: "I understand attest clients are excluded",
    confirmAllow: "Allow",
    cancel: "Cancel",
    toast: "Policy acceptance on · logged",
  },
  auto: {
    title: "Auto mode defaults",
    realFirm: "Auto mode isn't available for client data yet",
    help: "Auto mode dispatches an approved plan without asking again. Outputs still wait for a person.",
    rows: [
      ["ebp_audit", "EBP audits"],
      ["fs_audit", "Financial statement audits"],
      ["review_compilation", "Reviews & compilations"],
      ["preparation", "Preparation engagements"],
      ["tax_return", "Tax returns"],
      ["monthly_close", "Monthly closes"],
      ["notice", "Notices"],
      ["advisory", "Advisory projects"],
    ] as const,
  },
  data: {
    title: "Client data & §7216",
    consent: "Require §7216 AI consent before agents read return information",
    // T-01-T51: the count from C19's summary; the names live in the registry (ADM-05).
    consentHelp: (n: number) =>
      n === 0
        ? "Agents can read return information for every client with a consent on file."
        : `Agents cannot read return information today for ${String(n)} ${n === 1 ? "client" : "clients"}.`,
    registry: "Consent registry ›",
    template: "Consent template",
    templateValue:
      "BH §7216 Consent to Use v2 + BH §7216 Consent to Disclose — AI sub-processors v2 (separate documents, Rev. Proc. 2013-14 §5.05)",
    disclosure: "AI-use disclosure in engagement letters",
    region: "Processing region",
    regionValue: "United States",
    training: "Training on customer data",
    trainingValue: "Never",
    subProcessors: "Sub-processors",
    dpa: "DPA on file",
  },
  governance: {
    title: "Agent governance",
    install: "Install library agents",
    installValue: { manager_plus: "Manager and above", partner_only: "Partners only" },
    publish: "Publish a firm-made agent",
    publishValue: "Methodology owner approval (Margaret Okonkwo)",
    tolerance: "Override tolerance",
    toleranceHelp: "Agents above tolerance raise a QM finding in Quality (ADM-11).",
    sample: "Monthly accuracy sample",
    sampleValue: (n: number): string => `${String(n)} outputs per agent`,
    retention: "Run trace retention",
    retentionValue: (n: number): string => `${String(n)} years`,
  },
  sheet: {
    title: (n: number): string => `Save as v${String(n)}`,
    changes: "Change summary",
    tolerance: (from: number, to: number): string =>
      `Override tolerance ${String(from)}% → ${String(to)}%`,
    effective: "Effective",
    approver: "Approver",
    publish: (n: number): string => `Publish v${String(n)}`,
  },
  // The immediate-controls band (DV-3, DEC-411): v1 behaviour the handoff did not draw; the
  // words are SPEC-036's and SPEC-027's, as the legacy settings page says them.
  immediate: {
    title: "Immediate controls",
    clientData: "AI on your clients' data",
    on: (since: string, by: string): string => `On since ${since} · ${by}`,
    off: "Off",
    stages: "Agent stages",
    stage: { shadow: "Shadow (runs, not shown to your team yet)", live: "Live" },
    agentNames: {
      evidence_screening: "Evidence screening",
      upload_review: "Upload review",
    } as Record<string, string>,
    agents: "Engagement agents",
    running: "Running",
    paused: "Paused for the whole firm",
    pauseHelp:
      "Paused, no engagement agent screens, retrieves or suggests anything until resumed.",
    pause: "Pause all agents",
    resume: "Resume every agent",
    confirmPause: "Pause all agents?",
    // SPEC-036's opt-in (Q-02-T06), as the legacy setting words it; step-up is shell/mfa's.
    turnOnTitle: "Turn on AI on your clients' data?",
    turnOn: "Turn on",
    read: "I've read how our clients' data is handled",
    unavailable:
      "Not available yet. The agent runs on synthetic data only until the provider terms are in place.",
    whoRuns: "Who runs it",
    whoRunsValue: (provider: string, region: string): string =>
      `${provider}, in our own account, in the ${region} region (United States).`,
    yourData: "Your clients' data",
    yourDataValue: "Never used to train or improve models, and not kept after each request.",
    subprocessors: "Subprocessors",
    letter: "Suggested wording for your engagement letters",
    reviewedBy: "Terms reviewed by",
    stepUpTitle: "Confirm it's you",
    stepUpBody:
      "This action needs a recent sign-in. Sign in again, then try once more. If it still isn't allowed, your role doesn't permit it.",
    signIn: "Sign in again",
    cancel: "Cancel",
  },
  drawer: { title: "Version history", version: (n: number): string => `v${String(n)}` },
} as const;

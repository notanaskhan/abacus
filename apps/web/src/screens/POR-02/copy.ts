// POR-02 copy, verbatim from the handoff spec.md, revision.md and the built artboards
// (docs/screens/POR-02.md, Copy). The portal's words come from codes (ADR P-36): to-do kinds,
// stage codes, pill codes, team role codes and earlier-row kinds map to these strings. Names,
// counts and dates are data. The firm's name is the branding's, never a constant here.

import type {
  PortalHomeEarlierOut,
  PortalHomePillOut,
  PortalHomeStageOut,
  PortalHomeTeamMemberOut,
  PortalHomeTodoOut,
} from "@abacus/api-client";

const plural = (n: number, one: string, many: string): string => (n === 1 ? one : many);

export const COPY = {
  /** A planned target's hint in fixture builds (P-08 §2.2); production hides the control. */
  planned: "Not built yet",
  loading: "Loading",
  /** C-20's portal line (the kit's `errorBodyPortal`). */
  error: {
    title: "Couldn’t load your home.",
    body: "We could not reach the server. Nothing was lost; try again in a moment.",
    retry: "Retry",
  },
  rail: {
    title: "Your team",
    recent: "Recent messages",
    account: "Account & people",
    message: (name: string) => `Message ${name}`,
  },
  greeting: (first: string) => `Good morning, ${first}`,
  todo: {
    label: "To do",
    go: {
      upload: "Go to Documents →",
      answer: "Go to Questions →",
      deliverables: "Go to Deliverables →",
      sign: "Go to Sign →",
      reconnect: "Go to Connections →",
      approve: "Go to Approvals →",
    } as Readonly<Partial<Record<PortalHomeTodoOut["kind"], string>>>,
    upload: (n: number) => `Upload ${String(n)} ${plural(n, "document", "documents")}`,
    answer: (n: number) => `Answer ${String(n)} ${plural(n, "question", "questions")}`,
    nothingToSign: { title: "Nothing to sign yet", sub: "Your Form 8879 comes after our review." },
    ready: (n: number) => `${String(n)} documents ready`,
    nothingToApprove: {
      title: "Nothing to approve yet",
      sub: "Your August statements come to Approvals after our review.",
    },
    /** b: a first visit's cards read the request in full, with a line on what to do. */
    firstVisit: {
      sign: "Read and sign before we start on your 2025 return.",
      upload: "Drop files in your 2025 binder and they're sorted for you.",
    } as Readonly<Partial<Record<PortalHomeTodoOut["kind"], string>>>,
    overdue: (date: string) => `Overdue · due ${date}`,
    countLabel: (area: string, n: number) => `${area}, ${String(n)} to do`,
  },
  stages: {
    gather_documents: "Gather documents",
    prepare: "Prepare",
    review: "Review",
    sign_form_8879: "Sign Form 8879",
    file: "File",
    requests: "Requests",
    reconcile: "Reconcile",
    statements: "Statements",
    planning: "Planning",
    fieldwork: "Fieldwork",
    statements_review: "Statements review",
    report: "Report",
    scoping: "Scoping",
    system_description: "System description",
    testing: "Testing",
    exceptions: "Exceptions",
  } satisfies Record<PortalHomeStageOut["code"], string>,
  stageState: { done: "Done", current: "In progress", upcoming: "Not started" } satisfies Record<
    PortalHomeStageOut["state"],
    string
  >,
  pills: {
    getting_started: "We're getting started",
    preparing_return: "We're preparing your return",
    reviewing_return: "We're reviewing your return",
    reconciling_accounts: "We're reconciling your accounts",
    filed_and_accepted: "Filed and accepted",
    finishing_audit: "We're finishing your audit",
    testing_under_way: "Testing is under way",
  } satisfies Record<PortalHomePillOut["code"], string>,
  notes: {
    waiting_on_k1: (subject: string, firm: string, date: string) =>
      `We're waiting on one partnership K-1 (${subject}). ${firm} prepares it — nothing for you to do. Expected by ${date}.`,
    waiting_on_your_k1: (subject: string) => `Waiting on your K-1 from ${subject}.`,
  },
  team: {
    partner_signs_return: "Partner — signs your return",
    partner: "Partner",
    engagement_partner: "Engagement partner",
    manager_reviews_return: "Manager — reviews your return",
    manager: "Manager",
    preparer_day_to_day: "Preparer — your day-to-day contact",
    preparer: "Preparer",
    close_preparer: "Your close preparer",
    day_to_day_contact: "Your day-to-day contact",
    client_service: "Client service",
  } satisfies Record<PortalHomeTeamMemberOut["role_code"], string>,
  binder: {
    title: "Documents",
    done: (done: string, total: string) => `${done} of ${total} requests done`,
    sorted: (firm: string, n: string) => `${firm} sorted ${n} of your files`,
    open: "Open binder",
  },
  earlier: {
    title: "Earlier",
    view: "View",
    row: {
      extension_filed: (facts: Readonly<Record<string, string | number | boolean>>) =>
        `${String(facts.tax_year ?? "")} extension (Form ${String(facts.form ?? "")}) filed`,
      engagement_letter_signed: () =>
        "Engagement letter and §7216 consents (use · AI disclosure) signed",
      return_filed: (facts: Readonly<Record<string, string | number | boolean>>) =>
        `${String(facts.tax_year ?? "")} Form ${String(facts.form ?? "")} filed and accepted`,
      deliverable_released: () => "",
    } satisfies Record<
      PortalHomeEarlierOut["kind"],
      (facts: Readonly<Record<string, string | number | boolean>>) => string
    >,
  },
  welcome: {
    title: (firm: string) => `Welcome to ${firm}'s client portal.`,
    body: "Drop documents, answer questions and sign here — your team sees everything you send.",
    dismiss: "Dismiss welcome",
  },
  allSet: {
    title: "You're all set for now.",
    body: "We'll email you when your return is ready to sign.",
  },
} as const;

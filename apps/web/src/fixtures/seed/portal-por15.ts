// POR-15 · Governance room on fixtures (R-02-T21; docs/screens/POR-15.md): the handoff's letters,
// committee and inquiries for each artboard. Victoria Lam chairs Northwind's Benefits Committee; her
// `tcwg` grant opens the room and nothing of management's. The planning letter is AUD-22's approved
// letter word for word, minus the firm-side citation markers (spec.md). Synthetic only.
import type {
  CommitteeMemberOut,
  DeliverableRowOut,
  GovernanceCommunicationsOut,
  GovernanceLetterOut,
  GovernanceRoomsOut,
  RoomInquiriesOut,
} from "@abacus/api-client";
import { stableId } from "./prng";

export type Por15State = "a" | "b" | "c" | "d" | "e" | "f";

export const POR15_ID = {
  room: stableId("governance-body:northwind-benefits-committee"),
  planning: stableId("governance-communication:northwind-planning-260"),
  completion: stableId("governance-communication:northwind-completion-260"),
  control: stableId("governance-communication:northwind-265-703"),
  inquiries: stableId("questionnaire:northwind-tcwg-inquiries"),
  q1: stableId("question:northwind-tcwg-fraud-known"),
  q2: stableId("question:northwind-tcwg-fraud-oversight"),
  report: stableId("deliverable:northwind-auditor-report"),
  fs: stableId("deliverable:northwind-fs-py2025"),
} as const;

export function rooms(state: Por15State): GovernanceRoomsOut {
  return {
    items: [
      {
        id: POR15_ID.room,
        body_name: "Benefits Committee",
        subject: "Northwind Robotics 401(k) Plan · 2025 audit",
        member_role: "chair",
        questions_for_you: state === "f" ? 0 : 2,
      },
    ],
  };
}

function committee(state: Por15State): CommitteeMemberOut[] {
  const victoria = state === "a" || state === "c" || state === "f" ? null : "2026-09-21";
  return [
    { name: "Victoria Lam", member_role: "chair", acknowledged_on: victoria },
    {
      name: "Robert Haines",
      member_role: "member",
      acknowledged_on: state === "f" ? null : "2026-09-19",
    },
    {
      name: "Dana Kowalski",
      member_role: "member",
      acknowledged_on: state === "f" ? null : "2026-09-18",
    },
  ];
}

export function communications(state: Por15State): GovernanceCommunicationsOut {
  if (state === "f") {
    return {
      items: [{ id: null, title: "Planning communication", status: "not_yet", sent_on: null }],
      committee: committee(state),
    };
  }
  const planningAcked = state !== "a" && state !== "c";
  const items: GovernanceCommunicationsOut["items"] = [
    {
      id: POR15_ID.planning,
      title: "Planning communication",
      status: planningAcked ? "acknowledged" : "new",
      sent_on: "2026-09-18",
      acknowledged_on: planningAcked ? "2026-09-21" : null,
      due_on: null,
    },
    state === "d" || state === "e"
      ? {
          id: POR15_ID.completion,
          title: "Completion communication",
          status: "sent_acknowledged",
          sent_on: "2026-10-08",
          acknowledged_on: "2026-10-08",
          due_on: null,
        }
      : {
          id: null,
          title: "Completion communication",
          status: "not_yet",
          sent_on: null,
          acknowledged_on: null,
          due_on: "2026-10-09",
        },
    state === "d"
      ? {
          id: POR15_ID.control,
          title: "Internal control and reportable findings",
          status: "new",
          sent_on: "2026-11-20",
          acknowledged_on: null,
          due_on: "2026-12-08",
        }
      : {
          id: null,
          title: "Internal control and reportable findings",
          status: "not_yet",
          sent_on: null,
          acknowledged_on: null,
          due_on: null,
        },
  ];
  return { items, committee: committee(state) };
}

const PLANNING_SECTIONS: GovernanceLetterOut["sections"] = [
  { heading: null, body: "Our planned audit of the plan's 2025 financial statements" },
  {
    heading: "Our responsibilities",
    body: "We will audit the plan's financial statements as of December 31, 2025 and 2024 and for the year ended December 31, 2025, under auditing standards generally accepted in the United States of America. Management has elected an audit under ERISA section 103(a)(3)(C). For the investment information certified by Harborline Trust Company, we will perform the procedures AU-C 703 requires (comparing it to the certification and evaluating its presentation and disclosure) rather than audit it, and our report will describe this.",
  },
  {
    heading: "Planned scope and timing",
    body: "- Planning: September 14–18, 2026\n- Fieldwork: September 21 – October 2, 2026\n- Report expected: October 9, 2026\n- Form 5500 due: October 15, 2026 (extended with Form 5558)",
  },
  {
    heading: "Significant risks we identified",
    body: "- Management override of controls (presumed under auditing standards)\n- Contributions — completeness, cutoff and timeliness of remittances to the trust\n- Participant eligibility and automatic enrollment under the plan's QACA provisions\n\nWe rebutted the presumed risk of fraud in revenue recognition. The plan has no revenue transactions; contributions follow payroll and the plan's terms.",
  },
  {
    heading: "Our approach to internal control",
    body: "We will obtain an understanding of the controls over contributions, participant data and distributions, including those at Keystone Retirement Services. Keystone's SOC 1 Type 2 report covers October 1, 2024 to September 30, 2025, so we will ask for a bridge letter for the rest of 2025. We do not express an opinion on internal control.",
  },
  {
    heading: "Your input",
    body: "Please tell us about any fraud risks you are aware of, any late remittances, and any plan amendments or operational corrections since January 1, 2025.",
  },
];

const CONTROL_SECTIONS: GovernanceLetterOut["sections"] = [
  {
    heading: "Significant deficiency — Remittance of participant contributions",
    body: "The December 26, 2025 payroll ($48,600) was remitted on January 9, 2026; the remittance process has no backup approver.",
  },
  {
    heading: "Other deficiencies communicated to management",
    body: "Monitoring of service organizations; opt-out elections for auto-enrolled participants.",
  },
  {
    heading: "Reportable findings (AU-C 703)",
    body: "- Late remittance of participant contributions (corrected under VFCP)\n- Missed deferrals for 4 auto-enrolled participants\n- Safe-harbor match not computed on bonus pay as the plan's compensation definition requires",
  },
];

/** `GET /v1/portal/governance/communications/{id}` by artboard. */
export function letter(state: Por15State, id: string): GovernanceLetterOut | undefined {
  if (id === POR15_ID.planning && state !== "f") {
    const acked = state !== "a" && state !== "c";
    return {
      id,
      title: "Planning communication",
      dated_on: "2026-09-17",
      signed_by: "Margaret Okonkwo · Engagement Partner",
      sections: PLANNING_SECTIONS,
      status: acked ? "acknowledged" : "new",
      seen_hash: "fixture-planning-260-v1",
      committee: committee(state),
      allowed_actions: acked ? ["ask", "download"] : ["acknowledge", "ask", "download"],
    };
  }
  if (id === POR15_ID.control && state === "d") {
    return {
      id,
      title: "Internal control and reportable findings",
      dated_on: "2026-11-20",
      signed_by: "Margaret Okonkwo · Engagement Partner",
      sections: CONTROL_SECTIONS,
      status: "new",
      seen_hash: "fixture-265-703-v1",
      committee: committee(state).map((m) => ({ ...m, acknowledged_on: null })),
      allowed_actions: ["acknowledge", "ask", "download"],
    };
  }
  return undefined;
}

export function inquiries(state: Por15State): RoomInquiriesOut {
  if (state === "f") return { items: [] };
  return {
    items: [
      {
        questionnaire_id: POR15_ID.inquiries,
        question_id: POR15_ID.q1,
        prompt: "Do you know of any actual, suspected or alleged fraud affecting the plan?",
      },
      {
        questionnaire_id: POR15_ID.inquiries,
        question_id: POR15_ID.q2,
        prompt:
          "How does the committee oversee the way management identifies and responds to fraud risks in the plan?",
      },
    ],
  };
}

export function reports(state: Por15State): DeliverableRowOut[] {
  if (state !== "e" && state !== "d") return [];
  return [
    {
      id: POR15_ID.report,
      kind: "auditor_report",
      title: "Independent auditor's report",
      status: "final",
      restricted_use: false,
      latest_version: 1,
      page_count: 3,
      released_on: "2026-10-09",
    },
    {
      id: POR15_ID.fs,
      kind: "fs_final",
      title: "Financial statements and supplemental schedules",
      status: "final",
      restricted_use: false,
      latest_version: 5,
      page_count: 14,
      released_on: "2026-10-09",
    },
  ];
}

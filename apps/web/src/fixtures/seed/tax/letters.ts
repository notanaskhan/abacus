// Letters and client email for the T10 and TPL-10 specimens at E0 (F-06-T02): the Feld transmittal
// letter (T10c), the Harborview K-1 cover letter (T10d, locked while the return is out for
// signature), the Whitley document reminder (T10e, POR-20's email variant) and Ridgeline's ENG-04
// letter (TPL-10d). Verbatim from the handoff canvases (`Wave 0 - Foundations.dc.html#t10`,
// `Wave 0 - Templates.dc.html#tpl10`). These are template and clause blocks only: no block
// carries agent provenance while ADR P-25 is off (ADR-111, DEC-79). Specimen data for the gallery,
// not firm content: a firm's letters load through N-02's template import.

export type LetterBlock =
  | { kind: "meta"; section: string; text: string }
  | { kind: "h3" | "h4" | "p" | "li"; section: string; text: string }
  | { kind: "cta"; section: string; text: string }
  | { kind: "sign"; section: string; name: string; title: string }
  | { kind: "foot"; section: string; text: string };

export interface SectionToggle {
  id: string;
  label: string;
  on: boolean;
  reason: string;
}

export interface SeedLetter {
  key: string;
  title: string;
  context: string;
  sheet: string;
  sections: readonly SectionToggle[];
  variables: readonly { key: string; value: string; link?: boolean }[];
  blocks: readonly LetterBlock[];
  letterhead: boolean;
}

const t = (id: string, label: string, on: boolean, reason: string): SectionToggle => ({
  id,
  label,
  on,
  reason,
});

export const LETTERHEAD = {
  name: "Brightwater Hale LLP",
  chicago: "233 S Wacker Drive, Suite 4400 · Chicago, IL 60606",
  denverFooter: "Brightwater Hale LLP · 1700 Lincoln Street, Suite 2100, Denver, CO 80203",
} as const;

export const FELD_TRANSMITTAL: SeedLetter = {
  key: "feld-transmittal",
  title: "Transmittal Letter",
  context: "Jonah & Claire Feld",
  sheet: "Letters › Transmittal Letter",
  letterhead: true,
  sections: [
    t("greet", "Greeting and summary", true, "Always included"),
    t("bal", "Balance due and how to pay", true, "Balance due of 3,482"),
    t("est", "2026 estimated payments", true, "Safe harbor applies"),
    t("file", "Filing instructions", true, "E-file after you sign"),
    t("ext", "Extension notice", false, "Not on extension"),
  ],
  variables: [
    { key: "Client", value: "Jonah & Claire Feld", link: true },
    { key: "Salutation", value: "Dear Jonah and Claire" },
    { key: "Balance due", value: "3,482" },
    { key: "Pay by", value: "October 15, 2026" },
    { key: "Signer", value: "Daniel Reyes" },
    { key: "Prepared by", value: "Kevin Osei" },
  ],
  blocks: [
    { kind: "meta", section: "all", text: "September 12, 2026" },
    {
      kind: "meta",
      section: "all",
      text: "Jonah & Claire Feld\n2214 N Hoyne Avenue\nChicago, IL 60647",
    },
    { kind: "p", section: "greet", text: "Dear Jonah and Claire," },
    {
      kind: "p",
      section: "greet",
      text: "Your 2025 federal and Illinois income tax returns are ready for your review and signature. We prepared them from the documents you uploaded to your portal.",
    },
    { kind: "h4", section: "bal", text: "Balance due" },
    {
      kind: "p",
      section: "bal",
      text: "Your federal return shows a balance due of 3,482. Please pay by October 15, 2026 through IRS Direct Pay or with the enclosed voucher.",
    },
    { kind: "h4", section: "est", text: "2026 estimated payments" },
    {
      kind: "p",
      section: "est",
      text: "To avoid an underpayment penalty next year, we recommend four federal estimated payments of 2,950 each.",
    },
    { kind: "h4", section: "ext", text: "Extension" },
    {
      kind: "p",
      section: "ext",
      text: "We filed an extension for your return, so the filing deadline is October 15, 2026.",
    },
    { kind: "h4", section: "file", text: "Filing" },
    {
      kind: "p",
      section: "file",
      text: "Once you sign Form 8879 in the portal, we will file both returns electronically.",
    },
    {
      kind: "p",
      section: "greet",
      text: "Thank you for working with Brightwater Hale. Please reach out with any questions.",
    },
    { kind: "sign", section: "all", name: "Daniel Reyes, CPA", title: "Tax Partner" },
  ],
};

export const HARBORVIEW_K1_COVER: SeedLetter & { lockedReason: string } = {
  key: "harborview-k1-cover",
  title: "K-1 Cover Letter",
  context: "Harborview Dental Properties, LP",
  sheet: "Letters › K-1 Cover Letter",
  letterhead: true,
  lockedReason: "Out for signature since Sep 10",
  sections: [
    t("greet", "Greeting", true, "Always included"),
    t("k1", "What to do with your K-1", true, "All partners"),
    t("state", "State K-1s", true, "Illinois partners"),
    t("basis", "Basis reminder", false, "No losses this year"),
  ],
  variables: [
    { key: "Partnership", value: "Harborview Dental Properties, LP", link: true },
    { key: "Partners", value: "6" },
    { key: "Sent", value: "September 10, 2026" },
    { key: "Signer", value: "Daniel Reyes" },
  ],
  blocks: [
    { kind: "meta", section: "all", text: "September 10, 2026" },
    { kind: "meta", section: "all", text: "To the partners of Harborview Dental Properties, LP" },
    {
      kind: "p",
      section: "greet",
      text: "Enclosed is your 2025 Schedule K-1 (Form 1065) from Harborview Dental Properties, LP. Keep it with your 2025 tax records.",
    },
    { kind: "h4", section: "k1", text: "What to do with your K-1" },
    { kind: "li", section: "k1", text: "Give it to whoever prepares your 2025 return" },
    { kind: "li", section: "k1", text: "Report the amounts in boxes 1 and 2 on Schedule E" },
    { kind: "li", section: "k1", text: "Check Item L for your ending capital account" },
    { kind: "h4", section: "state", text: "State K-1s" },
    {
      kind: "p",
      section: "state",
      text: "Illinois partners also receive a Schedule K-1-P for their Illinois return.",
    },
    { kind: "h4", section: "basis", text: "Your basis" },
    {
      kind: "p",
      section: "basis",
      text: "Keep track of your basis, since it limits the losses you can deduct in later years.",
    },
    { kind: "sign", section: "all", name: "Daniel Reyes, CPA", title: "Tax Partner" },
  ],
};

export const WHITLEY_REMINDER: SeedLetter = {
  key: "whitley-reminder",
  title: "Document Reminder Email",
  context: "Marcus & Dana Whitley",
  sheet: "Client Email › Document Reminder",
  letterhead: false,
  sections: [
    t("greet", "Greeting", true, "Always included"),
    t("list", "Open requests", true, "5 still open"),
    t("due", "Due date reminder", true, "September 30"),
    t("cta", "Portal button", true, "Opens the binder"),
    t("help", "Questions line", false, "Off for reminders"),
  ],
  variables: [
    { key: "Client", value: "Marcus & Dana Whitley", link: true },
    { key: "Open requests", value: "5" },
    { key: "Due by", value: "September 30, 2026" },
    { key: "Button", value: "Open Your Binder" },
    { key: "From", value: "Kevin Osei" },
  ],
  blocks: [
    { kind: "h3", section: "all", text: "Your 2025 tax documents are due September 30" },
    {
      kind: "meta",
      section: "all",
      text: "From Kevin Osei, Brightwater Hale · to Marcus & Dana Whitley",
    },
    { kind: "p", section: "greet", text: "Hi Marcus and Dana," },
    { kind: "p", section: "list", text: "We still need these documents for your 2025 return:" },
    { kind: "li", section: "list", text: "2025 Form 1099-INT from Bellco Credit Union" },
    { kind: "li", section: "list", text: "2025 Property tax statement · Denver County" },
    { kind: "li", section: "list", text: "2025 Form 5498 from Fidelity Investments" },
    { kind: "li", section: "list", text: "2025 Form 5498-SA from HealthEquity" },
    { kind: "li", section: "list", text: "Receipts for gifts of $250 or more" },
    {
      kind: "p",
      section: "due",
      text: "Please upload them by September 30, 2026 so we can finish your return before the October 15 deadline.",
    },
    { kind: "cta", section: "cta", text: "Open Your Binder" },
    {
      kind: "p",
      section: "help",
      text: "Questions? Reply to this email and Kevin will get back to you.",
    },
    { kind: "foot", section: "all", text: LETTERHEAD.denverFooter },
  ],
};

export const RIDGELINE_ENG04: SeedLetter = {
  key: "ridgeline-eng04",
  title: "Engagement letter",
  context: "Ridgeline Property Partners, LP",
  sheet: "Letters › Engagement Letter",
  letterhead: true,
  sections: [
    t("scope", "Scope of services", true, "Always included"),
    t("k1", "Partner K-1s and composites", true, "5 partners"),
    t("s754", "§754 election", true, "Decision outstanding"),
    t("costseg", "Cost segregation study", false, "Separate advisory letter"),
    t("fees", "Fees and billing", true, "Fixed fee"),
    t("esign", "Electronic signature", true, "DocuSign"),
  ],
  variables: [
    { key: "Client", value: "Ridgeline Property Partners, LP", link: true },
    { key: "Addressee", value: "Ridgeline GP LLC, general partner" },
    { key: "Tax year", value: "2026" },
    { key: "Returns", value: "Form 1065 · IL, CO and NY" },
    { key: "Signer", value: "Daniel Reyes" },
    { key: "Preparer", value: "Olivia Brandt" },
  ],
  blocks: [
    { kind: "meta", section: "all", text: "September 14, 2026" },
    {
      kind: "meta",
      section: "all",
      text: "Ridgeline GP LLC\nGeneral partner, Ridgeline Property Partners, LP",
    },
    {
      kind: "p",
      section: "scope",
      text: "This letter confirms the tax services Brightwater Hale LLP will provide to Ridgeline Property Partners, LP for tax year 2026.",
    },
    { kind: "h4", section: "scope", text: "Scope of services" },
    {
      kind: "p",
      section: "scope",
      text: "We will prepare the 2026 Form 1065 and the Illinois, Colorado and New York partnership returns from the books and records you provide. Books are kept on the income-tax basis.",
    },
    { kind: "h4", section: "k1", text: "Partner K-1s" },
    {
      kind: "p",
      section: "k1",
      text: "We will prepare a Schedule K-1 for each of the five partners, and the state K-1s and composite filings each state requires.",
    },
    { kind: "h4", section: "s754", text: "§754 election" },
    {
      kind: "p",
      section: "s754",
      text: "Pell Street II LLC bought 5 points on June 30, 2025. We will advise on a §754 election and, if the partners make it, compute the §743(b) adjustment.",
    },
    { kind: "h4", section: "costseg", text: "Cost segregation study" },
    {
      kind: "p",
      section: "costseg",
      text: "A cost segregation study on Elm Street is a separate advisory engagement under its own letter.",
    },
    { kind: "h4", section: "fees", text: "Fees and billing" },
    {
      kind: "p",
      section: "fees",
      text: "Our fee is fixed and billed in three installments. Work outside this scope is billed separately, after you approve it.",
    },
    { kind: "h4", section: "esign", text: "Signature" },
    {
      kind: "p",
      section: "esign",
      text: "Please sign through DocuSign. Your signature confirms these terms.",
    },
    { kind: "sign", section: "all", name: "Daniel Reyes, CPA", title: "Tax Partner" },
  ],
};

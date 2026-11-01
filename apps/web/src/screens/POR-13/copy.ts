// POR-13 copy, verbatim from the handoff (screens/POR-13 spec.md) where it is not one recipient's
// data, under the portal's white label: never the product's name, never "pre-release" (T-02
// §3.8). The card's heading, figures, notes and documents come from the reads.

const FORM: Readonly<Record<string, string>> = {
  "1065": "1065",
  "1120s": "1120-S",
  "1041": "1041",
};

export const COPY = {
  active: "My K-1s",
  title: "My K-1s",
  heading: (issuer: string, year: number, form: string) =>
    `${issuer} — ${String(year)} Schedule K-1 (Form ${FORM[form] ?? form})`,
  amended: (year: number) => `Amended ${String(year)} K-1`,
  preparedBy: (firm: string) => `Prepared by ${firm}`,
  columns: { box: "Box", description: "Description", amount: "Amount" },
  amounts: "K-1 amounts",
  distributions: (year: number) => `Equals your ${String(year)} distributions`,
  help1041: (year: number) =>
    `Report these on your own ${String(year)} return (Schedule B and Form 1040). Qualified dividends are part of the ordinary dividends, not in addition to them.`,
  k3Included: "Schedule K-3 · Included",
  expected: (on: string) =>
    `Expected by ${on} — the partnership's extended due date. We'll email you when it's ready.`,
  expectedNoDate: "We'll email you when it's ready.",
  k3Title: "Schedule K-3",
  k3Body: (issuer: string) =>
    `${issuer} files Schedule K-3 for every partner this year. You only need it if you claim a foreign tax credit.`,
  documents: {
    k1: (form: string) => `Schedule K-1 (Form ${FORM[form] ?? form}) — PDF`,
    k3: (form: string) => `Schedule K-3 (Form ${FORM[form] ?? form})`,
    state: (codes: readonly string[]) =>
      codes.length === 1
        ? `${codes[0] ?? ""} Schedule K-1`
        : `State K-1s — ${codes.join(", ")} (${String(codes.length)})`,
    letter: (form: string) => (form === "1065" ? "Partner letter" : "Beneficiary letter"),
  },
  downloadAll: "Download all",
  downloadFailed: "The download didn't finish. Try again.",
  details: {
    title: "Your details",
    name: "Name",
    tin: "Taxpayer ID",
    address: "Mailing address",
    onFile: "On file",
    notOnFile: "Not on file",
    update: "Update…",
    help: (firm: string) => `Changes are checked by ${firm} before they're used on a K-1.`,
  },
  footer: (firm: string) =>
    `Questions about your K-1? Ask the trustee or ${firm} at the number in your beneficiary letter.`,
  roleUnion: "Your K-1s are in Deliverables › My K-1s",
  roleUnionTip: "Deliverables opens here once it is built (POR-09)",
  tinSheet: {
    title: "Update taxpayer ID",
    form: "Form",
    w9: "W-9",
    w8: "W-8",
    upload: "Upload a signed Form W-9",
    uploadW8Title: "Upload a signed Form W-8",
    failed: "The form wasn't sent. Try again.",
    uploadW8: "Foreign recipients: upload a signed Form W-8 instead.",
    choose: "Choose file…",
    helper: "We never show your full number on screen.",
    submit: "Send for review",
    sent: (firm: string) => `Sent. ${firm} checks it before it's used on a K-1.`,
  },
  addressSheet: {
    title: "Update mailing address",
    line1: "Address line 1",
    line2: "Address line 2",
    city: "City",
    state: "State",
    postal: "ZIP code",
    country: "Country",
    submit: "Send for review",
  },
  empty: "No K-1s here yet.",
  emptyBody: "We'll email you when your K-1 is ready.",
} as const;

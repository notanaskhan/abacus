// CLI-05 · Tax profile, authorizations & consents (T-01-T14, part 1): copy verbatim from the
// handoff's spec.md, with the screen contract's deviations: DF-16's recipient copy (from the
// provider register) and P-07's reveal words (domain/clients MaskedTin).

export const COPY = {
  back: "‹ All Clients",
  partnerLine: (partner: string, office: string): string => `Partner ${partner} · ${office}`,
  tabs: {
    label: "Client record",
    overview: "Overview",
    engagements: "Engagements",
    relationships: "Relationships",
    contacts: "Contacts & access",
    taxProfile: "Tax profile",
    files: "Files",
    messages: "Messages",
    activity: "Activity",
  },
  rail: {
    title: "Tax profile",
    elections: "Elections",
    authorizations: "Authorizations",
    consents: "Consents",
    transcripts: "Transcripts",
    noElections: "No elections on file",
    electionsOnFile: "On file",
    noTranscripts: "None yet",
    authorizationLine: (form: string, years: string): string =>
      `Form ${form} · ${years} · on file`,
    noAuthorization: "No 8821 or 2848 on file",
    consentLine: (status: string): string => `§7216 use · AI disclosure (2 consents) · ${status}`,
    openTip: "Opens in a later build",
  },
  notices: {
    band: "Open notices",
    count: (n: number): string => (n === 1 ? "1 open notice" : `${String(n)} open notices`),
    tip: "Opens NOT-02 · Notice workspace",
  },
  identity: {
    band: "Identity",
    taxpayer: "Taxpayer",
    spouse: "Spouse",
    portalUser: "Primary portal user",
    residentState: "Resident state",
  },
  sections: {
    label: "Tax profile sections",
    elections: "Elections",
    authorizations: "Authorizations",
    consents: "Consents",
    transcripts: "Transcripts",
  },
  consents: {
    title: "Consents",
    columns: {
      purpose: "Purpose",
      scope: "Scope",
      signed: "Signed",
      expires: "Expires",
      status: "Status",
    },
    setPurpose: "Use · AI disclosure (§7216, 2 consents)",
    offshore: "Disclosure to offshore preparers",
    notRequested: "Not requested",
    signed: "Signed",
    requested: (signed: number, of: number): string =>
      `Requested · ${String(signed)} of ${String(of)} signed`,
    // DF-16: the recipient from the provider register, never "Accrued Agent sub-processors".
    scope: (recipient: string, country: string): string =>
      `Return information disclosed to ${recipient} · model inference · ${country}`,
    document: {
      use: "Consent to use tax return information",
      ai_disclosure: "Consent to disclose tax return information to AI service providers",
    },
    note: "Each consent purpose is its own signed document, signed before use; a copy went to the taxpayers at signing (Rev. Proc. 2013-14 §§5.04–5.05).",
    request: "Request consent…",
    requestTip: "Opens SIG-02 · Envelope builder",
  },
  partial: {
    banner: (unsigned: string): string =>
      `§7216 consents (use · AI disclosure) partially signed — ${unsigned} has not signed. Agents cannot read return information until both sign (firm policy).`,
    resend: "Resend…",
    resendTip: "Opens SIG-01 · envelope E17",
  },
  // T-01-T34: Elections (e), Authorizations (c, g) and Transcripts (b), verbatim from the spec.
  elections: {
    title: "Elections",
    rows: {
      section_754: "§754",
      ptet: (year: number): string => `PTET TY${String(year)}`,
      bba_representative: "Partnership representative (BBA)",
      bba_opt_out: "Election out of BBA (§6221(b))",
      section_163j: "§163(j)",
      accounting_method: "Accounting method",
    } as const,
    pending754: (year: number): string =>
      `Not made — decision pending (due with the TY${String(year)} return)`,
    elected: "Elected",
    designated: "Designated",
    optOutNotEligible:
      "Not eligible — a partner is a partnership or disregarded entity for tax, which is not an eligible partner under §6221(b)(1)(C)",
    exempt163j: "Exempt — small business (average gross receipts under $31M)",
    // eslint-disable-next-line no-restricted-syntax -- the accounting method, not the product's name
    accrual: "Accrual",
    cash: "Cash",
  },
  authorizations: {
    title: "Authorizations",
    federal: "Federal",
    state: "State",
    form: (form: string): string => `Form ${form}`,
    formName: {
      "8821": "Tax information authorization",
      "2848": "Power of attorney and declaration of representative",
      state: "State authorization",
    } as const,
    designees: "Designees",
    designee: (name: string, last4: string | null): string =>
      last4 === null ? name : `${name} (CAF ••••${last4})`,
    taxMatters: "Tax matters",
    years: "Years",
    received: "Received",
    status: "Status",
    // The signers are the profile's taxpayers ("Marcus and Dana"), never copy.
    note8821: (signers: string): string =>
      `An 8821 lets us receive transcripts and notices, not represent. The CP2000 response will be signed by ${signers}, or file Form 2848 to represent them.`,
    draft2848: "Draft Form 2848…",
    draft2848Tip: "Opens SIG-02 · Envelope builder",
    stateOnFile: (code: string): string => `${code} · on file`,
    stateNotOnFile: (state: string): string => `${state} · not on file`,
    add: "+ Add",
    addTip: "Opens in a later build",
    none: "No 8821 or 2848 on file",
    request8821: "Request Form 8821…",
    request8821Tip: "Opens SIG-02 · Envelope builder",
  },
  transcripts: {
    title: "Transcripts",
    pulledHint:
      "Transcripts are pulled by a practitioner from IRS e-Services (TDS) under the 8821 and uploaded here",
    none: "No transcripts yet.",
    noneBody: "Pull them from IRS e-Services (TDS) under the 8821 on file, then upload here.",
    upload: "Upload transcript…",
    uploadTip: "Opens in a later build",
    // T-01-T50: Transcripts a, verbatim from the spec.
    compare: "Compare to return",
    compareTip: "Compares the selected transcript with the return as filed",
    comparing: "Comparing…",
    register: "Transcripts register",
    heads: ["Transcript", "Tax year", "Pulled", "Under", "Result"] as const,
    kind: {
      wage_income: "Wage & Income",
      account: "Account",
      record_of_account: "Record of Account",
    },
    pulled: (when: string, who: string): string => `${when} · ${who}`,
    under: (form: string): string => (form === "state" ? "State form" : `Form ${form}`),
    differences: (n: number): string => `${String(n)} ${n === 1 ? "difference" : "differences"}`,
    agrees: "Agrees to return",
    tc: (code: string, on: string): string => `TC ${code} · ${on}`,
    tcBalance: (code: string, on: string, balance: string): string =>
      `TC ${code} · ${on} · balance ${balance}`,
    failed: "Couldn't read",
    detail: (kind: string, year: number): string =>
      `${kind} · TY${String(year)} vs return as filed`,
    detailHeads: [
      "Information return",
      "Payer",
      "Transcript",
      "On return",
      "Difference",
      "Status",
    ] as const,
    form: (form: string): string => `Form ${form}`,
    notOnReturn: "Not on return",
    differs: "Differs",
    total: "Total difference",
    agreeingLine: (n: number, parts: readonly string[]): string =>
      `${String(n)} other information returns agree to the return (${parts.join(", ")}).`,
    agreeingPart: (form: string, count: number, times: boolean): string =>
      `${count > 1 ? "Forms" : "Form"} ${form}${times ? ` × ${String(count)}` : ""}`,
    allAgree: "Every information return agrees to the return.",
    notCompared: "Not compared yet.",
    why: "Why This Was Surfaced",
    openNotice: "Open notice analysis",
    openNoticeTip: "Opens NOT-02 · CP2000 · TY2024 · Marcus & Dana Whitley",
    flag: "Flag for review…",
    flagTip: "Opens in a later build",
    differenceTip: "Opens SHL-08 · Source viewer at the transcript line",
    railDifferences: (year: number, n: number): string =>
      `TY${String(year)} · ${String(n)} ${n === 1 ? "difference" : "differences"}`,
    railAgrees: (year: number): string => `TY${String(year)} · agrees to return`,
  },
  error: "The tax profile couldn't load.",
  retry: "Try again",
} as const;

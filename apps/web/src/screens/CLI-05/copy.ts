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
  error: "The tax profile couldn't load.",
  retry: "Try again",
} as const;

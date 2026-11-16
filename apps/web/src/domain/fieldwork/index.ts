// The fieldwork L3 kit's public entry (A-08-T26; AUD-12, AUD-13, AUD-14, AUD-26). It lives under
// `domain/audits/fieldwork` but is not re-exported by `domain/audits`: AUD-12 live uses it, and a
// re-export would put its code in the audits chunk every audit screen loads (the 140 KB route
// budget; TASK-8362).
export * from "../audits/fieldwork";

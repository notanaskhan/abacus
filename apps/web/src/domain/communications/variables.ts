// The email template variables as the editor shows them (R-01-T25; R-01 §4.7; POR-20): a chip
// reads `{client_first_name}` and is named "client first name, variable" for assistive tech. The
// whitelist itself is the server's (`GET /v1/firm/email-templates/{key}` `variables`).

/** "client_first_name" → "client first name". */
export function variableWords(name: string): string {
  return name.replaceAll("_", " ");
}

/** The chip's accessible name: "client first name, variable". */
export function variableLabel(name: string): string {
  return `${variableWords(name)}, variable`;
}

/** The token a template's text carries. */
export function token(name: string): string {
  return `{${name}}`;
}

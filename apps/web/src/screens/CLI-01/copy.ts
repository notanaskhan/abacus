// CLI-01 copy, verbatim from the handoff spec.md (docs/screens/CLI-01.md, Copy), with the amended
// header count (DEC-47) and no wall footer (DEC-43). Row text is data, never copy.

import type { ServiceLine } from "../../domain/clients";

export const COPY = {
  title: "Clients",
  noun: "clients",
  chips: {
    type: "Type",
    office: "Office",
    partner: "Partner",
    serviceLine: "Service line",
    status: "Status",
    all: "All",
    allOffices: "All offices",
  },
  search: "Search clients, entities, contacts",
  /** "184 clients" (DEC-47). */
  count: (total: string) => `${total} clients`,
  /** "Showing 3" (b). */
  showing: (n: string) => `Showing ${n}`,
  import: "Import…",
  importHint: "Opens CLI-06 in bulk import mode",
  /** "+ New client": the plus is the button's icon. */
  newClient: "New client",
  newClientHint: "Opens CLI-06 · new client",
  columns: {
    client: "Client",
    type: "Type",
    entities: "Entities",
    services: "Services",
    office: "Office",
    partner: "Partner",
    portal: "Portal",
    openRequests: "Open requests",
    lastActivity: "Last activity",
    menu: "Actions",
  },
  attest: "Attest",
  services: { tax: "Tax", audit: "Audit", cas: "CAS", advisory: "Advisory" } satisfies Record<
    ServiceLine,
    string
  >,
  none: "—",
  binderDraft: "Binder draft",
  loadMore: "Load more",
  /** "No clients match 'Schwab'." (d) */
  noMatch: (q: string) => `No clients match '${q}'.`,
  empty: {
    title: "No clients yet.",
    body: "Add a client or import your client list from CCH Axcess Tax or a CSV.",
  },
  menu: {
    label: (client: string) => `${client} actions`,
    open: "Open",
    message: "Message",
    newEngagement: "New engagement",
    copyId: "Copy client ID",
  },
  toast: { copied: "Client ID copied" },
} as const;

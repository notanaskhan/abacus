// The journey personas (ch. 04 §6.5; blueprint §9.2): the Brightwater Hale people a journey acts
// as, by slug (`?as=<slug>`). Names are the seed's (src/fixtures/seed/people.ts, portal.ts); all
// fictional. `walledFrom` is ADM-03's wall (Lena Park × Ashford Manufacturing Co.), which INV-3
// reads. A portal persona's scopes are the journey's to state (`InvariantContext.portalScopes`).

export type PersonaKind = "staff" | "portal" | "third_party";

export interface Persona {
  slug: string;
  name: string;
  kind: PersonaKind;
  /** Clients this person is walled from (INV-3). */
  walledFrom?: readonly string[];
}

const staff = (name: string, walledFrom?: readonly string[]): Persona => ({
  slug: slugOf(name),
  name,
  kind: "staff",
  ...(walledFrom === undefined ? {} : { walledFrom }),
});
const portal = (name: string, kind: PersonaKind = "portal"): Persona => ({
  slug: slugOf(name),
  name,
  kind,
});

/** "Hannah Leclerc" → "hannah-leclerc" (the seed's rule). */
export function slugOf(name: string): string {
  return name.toLowerCase().replace(/[^a-z]+/g, "-");
}

export const PERSONAS = {
  "margaret-okonkwo": staff("Margaret Okonkwo"),
  "daniel-reyes": staff("Daniel Reyes"),
  "priya-raman": staff("Priya Raman"),
  "thomas-whitcombe": staff("Thomas Whitcombe"),
  "hannah-leclerc": staff("Hannah Leclerc"),
  "samuel-ito": staff("Samuel Ito"),
  "olivia-brandt": staff("Olivia Brandt"),
  "marcus-delaney": staff("Marcus Delaney"),
  "ana-cruz": staff("Ana Cruz"),
  "kevin-osei": staff("Kevin Osei"),
  "lena-park": staff("Lena Park", ["Ashford Manufacturing Co."]),
  "raj-malhotra": staff("Raj Malhotra"),
  "grace-holloway": staff("Grace Holloway"),
  "felix-andersen": staff("Felix Andersen"),
  "cole-hart": staff("Cole Hart"),
  "dina-sato": staff("Dina Sato"), // F-06-T02: TPL-16e names her; the E6 preparer
  "laura-kemp": staff("Laura Kemp"), // ENG-13 a, b and e (P-07-T62)
  "caleb-dunn": staff("Caleb Dunn"), // A-03-T19: AUD-31 f and e′ (j04 2)
  "simone-baptiste": staff("Simone Baptiste"), // A-03-T19: AUD-11 f (j22 2)
  "claire-feld": portal("Claire Feld"),
  "dana-kowalski": portal("Dana Kowalski"),
  "tess-moreno": portal("Tess Moreno"),
  "owen-calder": portal("Owen Calder"), // N-02-T40: Ridgeline GP signs the letter on POR-06 (j15 4)
  "luis-ferrante": portal("Luis Ferrante"),
  "meera-shah": portal("Meera Shah"),
  "mira-kapoor": portal("Mira Kapoor"), // F-06-T02: the TPL-16 signer on envelope E6
  "sam-ortiz": portal("Sam Ortiz", "third_party"),
  // T-02-T32: the two K-1-only people of T-02 §1 (seed/portal-k1s.ts); the member has no name.
  "nora-calloway": portal("Nora Calloway"),
  "pell-street-member": {
    slug: "pell-street-member",
    name: "Pell Street Ventures LLC · authorized member",
    kind: "portal",
  },
} as const satisfies Record<string, Persona>;

export type PersonaSlug = keyof typeof PERSONAS;

export function persona(slug: PersonaSlug): Persona {
  return PERSONAS[slug];
}

/** E0: Mon 14 Sep 2026, 9:24 AM CT (SPEC-307 AC-1), the clock a fixture journey stands at. */
export const DEMO_INSTANT = "2026-09-14T09:24:00-05:00";

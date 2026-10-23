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
  "claire-feld": portal("Claire Feld"),
  "dana-kowalski": portal("Dana Kowalski"),
  "luis-ferrante": portal("Luis Ferrante"),
  "meera-shah": portal("Meera Shah"),
  "sam-ortiz": portal("Sam Ortiz", "third_party"),
} as const satisfies Record<string, Persona>;

export type PersonaSlug = keyof typeof PERSONAS;

export function persona(slug: PersonaSlug): Persona {
  return PERSONAS[slug];
}

/** E0: Mon 14 Sep 2026, 9:24 AM CT (SPEC-307 AC-1), the clock a fixture journey stands at. */
export const DEMO_INSTANT = "2026-09-14T09:24:00-05:00";

// The 184 clients of Brightwater Hale LLP at E0 (SPEC-307 AC-1): 16 named (blueprint 01 §9.3 and
// the CLI-01 rows), 66 roster clients (§9.7 tax returns, closes, audits and signature envelopes)
// and 102 deterministic filler clients that never reuse a canonical surname or word. Every name is
// fictional. No client carries an identifier of any kind.

import { Rng, stableId } from "./prng";
import { type OfficeName, SEATS } from "./people";

export type ClientKind =
  | "individual"
  | "household"
  | "business"
  | "partnership"
  | "exempt_org"
  | "trust"
  | "estate"
  | "plan";
export type Portal = "active" | "invited" | "not_invited";
export type ServiceLine = "tax" | "audit" | "cas" | "advisory";
export type ClientOrigin = "named" | "roster" | "filler";

export interface SeedClient {
  /** A stable slug, the label every id for this client is derived from. */
  slug: string;
  name: string;
  kind: ClientKind;
  origin: ClientOrigin;
  office: OfficeName;
  /** The relationship partner's initials (a seat holder). */
  partner: string;
  services: ServiceLine[];
  /** Audit and review clients (CLI-01 "Attest" tag). */
  attest: boolean;
  portal: Portal;
  /** Entity names; the first is the primary entity (the client itself unless stated). */
  entities: string[];
  /** CLI-01 order for the 16 named clients (1 = most recent activity); null otherwise. */
  recency: number | null;
}

interface Named {
  name: string;
  kind: ClientKind;
  office: OfficeName;
  partner: string;
  services: ServiceLine[];
  attest?: boolean;
  portal?: Portal;
  entities?: string[];
}

// CLI-01 rows 1 to 16, newest activity first (the screen's order).
const NAMED: readonly Named[] = [
  {
    name: "Jonah & Claire Feld",
    kind: "household",
    office: "New York",
    partner: "DR",
    services: ["tax"],
  },
  {
    name: "Copperleaf Coffee Roasters, Inc.",
    kind: "business",
    office: "Denver",
    partner: "PR",
    services: ["cas", "tax"],
  },
  { name: "Meera Shah", kind: "individual", office: "Chicago", partner: "NA", services: ["tax"] },
  {
    name: "Northwind Robotics, Inc.",
    kind: "business",
    office: "Chicago",
    partner: "MO",
    services: ["audit"],
    attest: true,
    entities: ["Northwind Robotics, Inc.", "Northwind Robotics 401(k) Plan"],
  },
  {
    name: "Ridgeline Property Partners, LP",
    kind: "partnership",
    office: "New York",
    partner: "DR",
    services: ["tax", "advisory"],
  },
  {
    name: "Granite Peak Outdoor Supply, Inc.",
    kind: "business",
    office: "Denver",
    partner: "MO",
    services: ["audit"],
    attest: true,
    entities: ["Granite Peak Outdoor Supply, Inc.", "Granite Peak Outdoor Supply 401(k) Plan"],
  },
  {
    name: "Harborview Dental Properties, LP",
    kind: "partnership",
    office: "New York",
    partner: "DR",
    services: ["tax"],
  },
  {
    name: "Marcus & Dana Whitley",
    kind: "household",
    office: "Denver",
    partner: "DR",
    services: ["tax"],
  },
  {
    name: "Estate of Walter Thornbury",
    kind: "estate",
    office: "Chicago",
    partner: "DR",
    services: ["tax"],
    portal: "invited",
    entities: ["Walter Thornbury", "Estate of Walter Thornbury"],
  },
  {
    name: "Bluestem Analytics, LLC",
    kind: "business",
    office: "New York",
    partner: "PR",
    services: ["tax", "cas"],
  },
  {
    name: "Lakeshore Literacy Alliance",
    kind: "exempt_org",
    office: "Chicago",
    partner: "CM",
    services: ["audit", "tax"],
    attest: true,
  },
  { name: "Elena Varga", kind: "individual", office: "Chicago", partner: "NA", services: ["tax"] },
  {
    name: "Calloway Family Trust",
    kind: "trust",
    office: "Chicago",
    partner: "DR",
    services: ["tax"],
  },
  {
    name: "Ashford Manufacturing Co.",
    kind: "business",
    office: "Chicago",
    partner: "NA",
    services: ["tax"],
  },
  {
    name: "Juniper & Oak Interiors, LLC",
    kind: "business",
    office: "Denver",
    partner: "PR",
    services: ["cas"],
  },
  {
    name: "Daniel & Ruth Okafor",
    kind: "household",
    office: "Chicago",
    partner: "NA",
    services: ["tax"],
  },
];

// A roster row: [name, kind, office (null: derived from the client's name), service lines].
type Roster = readonly [string, ClientKind, OfficeName | null, readonly ServiceLine[]];

const T: readonly ServiceLine[] = ["tax"];
const TC: readonly ServiceLine[] = ["tax", "cas"];
const TA: readonly ServiceLine[] = ["tax", "audit"];
const C: readonly ServiceLine[] = ["cas"];
const CA: readonly ServiceLine[] = ["cas", "audit"];
const A: readonly ServiceLine[] = ["audit"];

const ROSTER: readonly Roster[] = [
  // §9.7 tax returns R1 to R30 (office as the table gives it); R11, R15 to R18 and R28 are also closes.
  ["Mateo & Lucia Alvarez", "household", "Chicago", T],
  ["Priyanka & Sam Iyer", "household", "New York", T],
  ["Harold Stein", "individual", "Chicago", T],
  ["Wren & Avery Collins", "household", "Denver", T],
  ["Gloria Mendez", "individual", "Denver", T],
  ["Thomas & Irene Kowal", "household", "Chicago", T],
  ["Benjamin Osterberg", "individual", "New York", T],
  ["Nina & Paul Haddox", "household", "Chicago", T],
  ["Rafael Quintero", "individual", "Denver", T],
  ["Sunil & Asha Rao", "household", "New York", T],
  ["Cedar Hollow Farms, LLC", "partnership", "Denver", TC],
  ["Northgate Medical Partners, LLP", "partnership", "Chicago", T],
  ["Marlowe Street Holdings, LP", "partnership", "New York", T],
  ["Kestrel Ventures Fund I, LP", "partnership", "New York", T],
  ["Bramble & Finch Design, LLC", "partnership", "Chicago", TC],
  ["Two Rivers Brewing Co.", "business", "Denver", TC],
  ["Summit Line Logistics, Inc.", "business", "Chicago", TC],
  ["Pinecrest Pediatrics, PC", "business", "Denver", TC],
  ["Oakline Software, Inc.", "business", "New York", TA],
  ["Meridian Tool & Die, Inc.", "business", "Chicago", TA],
  ["Fenwick Family Foundation", "exempt_org", "Chicago", TA],
  ["Riverbend Community Theater", "exempt_org", "Denver", TA],
  ["Pryor Irrevocable Trust", "trust", "Chicago", T],
  ["Estate of Eugene Barlow", "estate", "New York", T],
  ["Delia Fortune", "individual", "Denver", T],
  ["Morgan & Kai Ferris", "household", "New York", T],
  ["Aurelio Santos", "individual", "Chicago", T],
  ["Hollis Creek Veterinary, PC", "business", "Denver", TC],
  ["Vantage Point Realty, LLC", "partnership", "Chicago", T],
  ["Juliet Okonjo", "individual", "Chicago", T],
  // §9.7 closes C1 to C22 that are not already above or named (office: the close preparer's).
  ["Larkspur Floral, Inc.", "business", "Chicago", TC],
  ["Alder & Ash Furniture Co.", "business", "Chicago", C],
  ["Bluebird Bakery Co.", "business", "Chicago", C],
  ["Canyon Pass Climbing Gym, LLC", "business", "Denver", C],
  ["Foxglove Studio, LLC", "business", "Chicago", C],
  ["Granary Row Market, Inc.", "business", "Chicago", C],
  ["Ironwood Landscape Co.", "business", "Denver", C],
  ["Kettle & Kiln Pottery, LLC", "business", "Chicago", CA],
  ["Lumen Dental Lab, Inc.", "business", "Denver", C],
  ["Maple & Main Hardware, Inc.", "business", "Chicago", C],
  ["Northfield Pet Clinic, PC", "business", "Denver", C],
  ["Orchard Lane Wellness, LLC", "business", "Chicago", C],
  ["Prairie Wind Solar Installers, Inc.", "business", "Denver", C],
  ["Quill & Press Printing Co.", "business", "Chicago", C],
  // §9.7 audits A1 to A27 whose client is not already above or named.
  ["Cobalt Ridge Manufacturing 401(k) Plan", "plan", null, A],
  ["Halden Health 403(b) Plan", "plan", null, A],
  ["Fairhaven Foods 401(k) Plan", "plan", "Chicago", A],
  ["Sterling Freight 401(k) Plan", "plan", null, A],
  ["Westbrook Engineering 401(k) Plan", "plan", null, A],
  ["Arbor Senior Living 401(k) Plan", "plan", null, A],
  ["Keel & Compass Marine 401(k) Plan", "plan", null, A],
  ["Redtail Construction 401(k) Plan", "plan", null, A],
  ["Clearwater Credit Union 401(k) Plan", "plan", null, A],
  ["Hearthstone Hospitality 401(k) Plan", "plan", null, A],
  ["Bayside Electric Cooperative 401(k) Plan", "plan", null, A],
  ["Tamarack Health System 403(b) Plan", "plan", null, A],
  ["Larimer Cooperative Grocery", "business", null, A],
  ["Sable Creek Homeowners Association", "exempt_org", null, A],
  ["Halcyon Foods Distribution, Inc.", "business", null, A],
  ["Hillcrest Montessori School", "exempt_org", null, A],
  ["Wildflower Land Trust", "exempt_org", null, A],
  // §9.7 signature envelopes E5 to E10 whose signer is not already above.
  ["Corinne Abbott", "individual", null, T],
  ["Dev & Mira Kapoor", "household", null, T],
  ["Hugo Brandvold", "individual", null, T],
  ["Noor & Adam Farouk", "household", null, T],
  ["Brightline Optics, Inc.", "business", null, T],
];

const OFFICE_NAMES: readonly OfficeName[] = ["Chicago", "Denver", "New York"];
// The returns split of §9.1 (98 / 64 / 62 of 224), as cumulative cut points over [0, 1).
function drawOffice(rng: Rng): OfficeName {
  const x = rng.next();
  return x < 98 / 224 ? "Chicago" : x < 162 / 224 ? "Denver" : "New York";
}

const TAX_PARTNER: Record<OfficeName, string> = { Chicago: "NA", Denver: "VH", "New York": "DR" };

function partnerFor(services: readonly ServiceLine[], office: OfficeName, ep: string): string {
  if (services.includes("audit")) return ep;
  if (services.includes("cas") && !services.includes("tax")) return "PR";
  return TAX_PARTNER[office];
}

function portalFor(rng: Rng): Portal {
  const x = rng.next();
  return x < 0.7 ? "active" : x < 0.85 ? "invited" : "not_invited";
}

// The audit partner of each audit-only roster client (blueprint §9.7 A5 to A27, the EP column).
const AUDIT_PARTNER: Readonly<Record<string, string>> = {
  "Cobalt Ridge Manufacturing 401(k) Plan": "TW",
  "Halden Health 403(b) Plan": "CM",
  "Fairhaven Foods 401(k) Plan": "MO",
  "Sterling Freight 401(k) Plan": "TW",
  "Westbrook Engineering 401(k) Plan": "CM",
  "Arbor Senior Living 401(k) Plan": "MO",
  "Keel & Compass Marine 401(k) Plan": "TW",
  "Redtail Construction 401(k) Plan": "CM",
  "Clearwater Credit Union 401(k) Plan": "MO",
  "Hearthstone Hospitality 401(k) Plan": "TW",
  "Bayside Electric Cooperative 401(k) Plan": "CM",
  "Tamarack Health System 403(b) Plan": "CM",
  "Larimer Cooperative Grocery": "TW",
  "Sable Creek Homeowners Association": "CM",
  "Halcyon Foods Distribution, Inc.": "TW",
  "Hillcrest Montessori School": "TW",
  "Wildflower Land Trust": "CM",
  "Oakline Software, Inc.": "CM",
  "Meridian Tool & Die, Inc.": "MO",
  "Riverbend Community Theater": "CM",
  "Fenwick Family Foundation": "PR",
  "Kettle & Kiln Pottery, LLC": "PR",
};

export function slugOfClient(name: string): string {
  return name
    .toLowerCase()
    .replace(/&/g, " and ")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

/** The id of one of a client's entities (the client itself, a plan, an estate). */
export function entityIdOf(clientSlug: string, entityName: string): string {
  return stableId(`entity:${clientSlug}:${slugOfClient(entityName)}`);
}

// Words that are generic enough to repeat (company forms and descriptors); everything else a
// canonical name uses is reserved, so a filler client can never echo a featured or roster one.
const GENERIC = new Set(
  "inc llc llp pc lp the and plan trust family estate partners holdings foundation group company".split(
    " ",
  ),
);

function words(text: string): string[] {
  return text
    .toLowerCase()
    .split(/[^a-z]+/)
    .filter((w) => w.length >= 3 && !GENERIC.has(w));
}

const FIRST = (
  "Adrian Beatrice Colin Delphine Edmund Farah Gideon Honora Ignatius Josephine Kaito Leontine " +
  "Matteo Nadira Orson Philippa Quentin Rowena Soren Tamsin Ulrich Vesna Wendell Xiomara Yuri " +
  "Zelda Abel Bryn Cyrus Dalia Emeric Freya Gus Hollis Ilona Jules Kit Lorna Milo Neve Otis Pia"
).split(" ");

const LAST = (
  "Abernathy Bellamy Castellano Dunmore Eastwood Fairbanks Galloway Hartwell Ingram Jessup Kingsley " +
  "Lockhart Montrose Nakamura Oyelaran Prescott Quigley Radcliffe Sandoval Thackeray Underhill " +
  "Vasquez Winslow Yarborough Zimmerman Ackerman Blackwood Carrow Delacroix Everhart Fontaine " +
  "Gladstone Hollander Ivanov Jarrett Kessler Lindqvist Merriweather Nightingale Oswald Pemberton " +
  "Quinlan Rutherford Stanhope Tennant Ulloa Vandermeer Wexford Xavier Yoshida Zeller Ashby " +
  "Marchetti Cantrell Dempsey Elmsworth Farnsworth Grayson Haverford Isley Jernigan Brantley " +
  "Lavigne Mortimer Nolan Overby Pritchard Rennick Sutherland Tolliver Upshaw Valentin Whitaker"
).split(" ");

const WORD_A = (
  "Amber Birchwood Cinder Driftwood Ember Fernhill Gable Hazel Indigo Linden Larch Marigold " +
  "Nutmeg Opal Pebble Quince Russet Sorrel Thistle Umber Violet Willow Yarrow Zephyr Alcove " +
  "Beacon Cobble Dovetail Eddy Fable Gilded Hearth Inlet Jasper Kindle Lantern Meadow Nimbus " +
  "Orchid Plover Quarry Ripple Sparrow Tideway Upland Verdant Wren Saltmarsh Brindle Clover"
).split(" ");

const NOUN = (
  "Cabinetry Pottery Provisions Cycles Textiles Optics Printing Outfitters Supply Freight " +
  "Interiors Orchards Roasters Kitchens Press Milling Glassworks Lighting Tailoring Fabrication " +
  "Ceramics Forge Salvage Cartage Apiaries Creamery Distillers Joinery Masonry Plumbing Surveying " +
  "Tutoring Imaging Rentals Storage"
).split(" ");

const SUFFIX = [", LLC", ", Inc.", " Co.", ", PC"] as const;

/** The words and surnames the canonical (named and roster) clients and the staff already use. */
function canonicalWords(names: readonly string[]): Set<string> {
  const all = new Set<string>();
  for (const name of names) for (const w of words(name)) all.add(w);
  for (const seat of SEATS) for (const w of words(seat.name)) all.add(w);
  return all;
}

function fillerName(rng: Rng, kind: ClientKind): string {
  if (kind === "individual") return `${rng.pick(FIRST)} ${rng.pick(LAST)}`;
  if (kind === "household") {
    const first = rng.pick(FIRST);
    const second = rng.pick(FIRST);
    return `${first} & ${second === first ? "Jules" : second} ${rng.pick(LAST)}`;
  }
  const head = rng.chance(0.5) ? `${rng.pick(WORD_A)} & ${rng.pick(WORD_A)}` : rng.pick(WORD_A);
  const tail = `${head} ${rng.pick(NOUN)}`;
  const suffix = rng.pick(SUFFIX);
  return kind === "partnership" ? `${tail}, LP` : `${tail}${suffix}`;
}

function drawKind(rng: Rng): ClientKind {
  const x = rng.next();
  return x < 0.25 ? "individual" : x < 0.6 ? "household" : x < 0.9 ? "business" : "partnership";
}

/** `count` filler clients, deterministic, none sharing a word with a canonical client or staff. */
function fillers(canonical: readonly string[], count: number): SeedClient[] {
  const reserved = canonicalWords(canonical);
  const taken = new Set(canonical.map((n) => n.toLowerCase()));
  const out: SeedClient[] = [];
  for (let i = 0; out.length < count; i += 1) {
    if (i > 5000) throw new Error("filler pools are exhausted");
    const rng = new Rng(`filler:${String(i)}`);
    const kind = drawKind(rng);
    const name = fillerName(rng, kind);
    const lower = name.toLowerCase();
    if (taken.has(lower) || words(name).some((w) => reserved.has(w))) continue;
    taken.add(lower);
    const office = drawOffice(rng);
    const services: ServiceLine[] =
      kind === "business" && rng.chance(0.3) ? ["tax", "cas"] : ["tax"];
    out.push({
      slug: slugOfClient(name),
      name,
      kind,
      origin: "filler",
      office,
      partner: partnerFor(services, office, "PR"),
      services,
      attest: false,
      portal: portalFor(rng),
      entities: [name],
      recency: null,
    });
  }
  return out;
}

export const NAMED_COUNT = NAMED.length;
export const ROSTER_COUNT = ROSTER.length;
export const FILLER_COUNT = 102;

/** All 184 clients: the 16 named (CLI-01 order), then the 66 roster, then the 102 filler. */
export function buildClients(): SeedClient[] {
  const named: SeedClient[] = NAMED.map((n, index) => ({
    slug: slugOfClient(n.name),
    name: n.name,
    kind: n.kind,
    origin: "named",
    office: n.office,
    partner: n.partner,
    services: [...n.services],
    attest: n.attest ?? false,
    portal: n.portal ?? "active",
    entities: n.entities ?? [n.name],
    recency: index + 1,
  }));
  const roster: SeedClient[] = ROSTER.map(([name, kind, office, services]) => {
    const rng = new Rng(`roster:${name}`);
    const chosen = office ?? rng.pick(OFFICE_NAMES);
    return {
      slug: slugOfClient(name),
      name,
      kind,
      origin: "roster",
      office: chosen,
      partner: partnerFor(services, chosen, AUDIT_PARTNER[name] ?? "MO"),
      services: [...services],
      attest:
        services.includes("audit") &&
        !["Fenwick Family Foundation", "Kettle & Kiln Pottery, LLC"].includes(name),
      portal: portalFor(rng),
      entities: [name],
      recency: null,
    };
  });
  return [
    ...named,
    ...roster,
    ...fillers(
      [...named, ...roster].map((c) => c.name),
      FILLER_COUNT,
    ),
  ];
}

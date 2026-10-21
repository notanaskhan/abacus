// The 46 Accrued seats of Brightwater Hale LLP (blueprint 01 §9.1 and §9.2; ADM-02 spec, rows 1 to
// 46, in the screen's order). 14 are named in the seed and 32 come from the §9.2 generator list.
// All names are fictional. Emails are first.last@brightwaterhale.com as ADM-02 shows them;
// delivery is always rewritten to the synthetic sink (SPEC-307 AC-5).

export type OfficeName = "Chicago" | "Denver" | "New York";

export type SeatRole =
  | "Partner"
  | "Manager"
  | "Tax Reviewer"
  | "Senior"
  | "Staff"
  | "Tax Preparer"
  | "Firm Admin"
  | "IT / Security";

export interface Seat {
  /** 1 to 46: the row number on ADM-02. */
  n: number;
  initials: string;
  name: string;
  role: SeatRole;
  /** The line under the role on ADM-02 ("Managing Partner, QM owner"). */
  title: string;
  office: OfficeName;
  /** One of the 14 people the seed names (§9.2); the rest are generator seat holders. */
  named: boolean;
  seasonal: boolean;
}

type Row = readonly [
  initials: string,
  name: string,
  role: SeatRole,
  title: string,
  office: OfficeName,
  flags?: "named" | "seasonal" | "named-seasonal",
];

const ROWS: readonly Row[] = [
  ["MO", "Margaret Okonkwo", "Partner", "Managing Partner, QM owner", "Chicago", "named"],
  ["DR", "Daniel Reyes", "Partner", "Tax (signer)", "New York", "named"],
  ["PR", "Priya Raman", "Partner", "CAS & Advisory", "Denver", "named"],
  ["TW", "Thomas Whitcombe", "Partner", "EQR", "Chicago", "named"],
  ["VH", "Victor Hammond", "Partner", "Tax", "Denver"],
  ["CM", "Celia Marsh", "Partner", "Audit", "New York"],
  ["NA", "Neil Ashcroft", "Partner", "Tax", "Chicago"],
  ["HL", "Hannah Leclerc", "Manager", "Audit Senior Manager", "Chicago", "named"],
  ["SI", "Samuel Ito", "Tax Reviewer", "Tax Manager", "New York", "named"],
  ["LK", "Laura Kemp", "Manager", "Audit", "Chicago"],
  ["OH", "Omar Haddad", "Manager", "Audit", "Chicago"],
  ["IM", "Isaac Moreau", "Tax Reviewer", "Tax Manager", "Denver"],
  ["TR", "Tanya Reed", "Tax Reviewer", "Tax Manager", "New York"],
  ["HV", "Helen Voss", "Manager", "CAS", "Denver"],
  ["OB", "Olivia Brandt", "Senior", "Tax (preparer, first-level reviewer)", "Denver", "named"],
  ["MD", "Marcus Delaney", "Senior", "Audit in-charge", "Chicago", "named"],
  ["RM", "Raj Malhotra", "Senior", "CAS", "Denver", "named"],
  ["CD", "Caleb Dunn", "Senior", "Audit", "Chicago"],
  ["JB", "Jasper Bell", "Senior", "Audit", "Chicago"],
  ["SB", "Simone Baptiste", "Senior", "Audit", "Denver"],
  ["YK", "Yusuf Kaya", "Tax Reviewer", "Tax Senior", "Chicago"],
  ["NP", "Nadia Petrov", "Tax Reviewer", "Tax Senior", "New York"],
  ["QL", "Quinn Lowry", "Tax Reviewer", "Tax Senior", "New York"],
  ["EW", "Erin Walsh", "Senior", "CAS", "Denver"],
  ["RF", "Rosa Fuentes", "Senior", "CAS", "Chicago"],
  ["AC", "Ana Cruz", "Staff", "Audit", "Chicago", "named"],
  ["KO", "Kevin Osei", "Tax Preparer", "Tax", "New York", "named"],
  ["AW", "Aiden Ward", "Staff", "Audit", "Chicago"],
  ["FN", "Fiona Nash", "Staff", "Audit", "Chicago"],
  ["KR", "Kira Ross", "Staff", "Audit", "Chicago"],
  ["CH", "Cole Hart", "Staff", "Audit", "Denver"],
  ["HP", "Hana Pruitt", "Staff", "Audit", "New York"],
  ["BN", "Bianca Novak", "Tax Preparer", "Tax", "Chicago"],
  ["GT", "Gabe Torres", "Tax Preparer", "Tax", "Chicago"],
  ["JL", "Joel Lim", "Tax Preparer", "Tax", "Denver"],
  ["LW", "Leo Wong", "Tax Preparer", "Tax", "Denver"],
  ["DS", "Dina Sato", "Tax Preparer", "Tax", "New York"],
  ["IV", "Ivy Vance", "Staff", "CAS", "Chicago"],
  ["EG", "Ezra Gold", "Staff", "CAS", "Denver"],
  ["LP", "Lena Park", "Tax Preparer", "Tax (seasonal)", "Denver", "named-seasonal"],
  ["MA", "Maya Adler", "Tax Preparer", "Tax (seasonal)", "Chicago", "seasonal"],
  ["PS", "Paige Sutton", "Tax Preparer", "Tax (seasonal)", "Chicago", "seasonal"],
  ["NK", "Noel Kirby", "Tax Preparer", "Tax (seasonal)", "Denver", "seasonal"],
  ["RV", "Remy Vidal", "Tax Preparer", "Tax (seasonal)", "New York", "seasonal"],
  ["GH", "Grace Holloway", "Firm Admin", "Client Service Coordinator", "Chicago", "named"],
  ["FA", "Felix Andersen", "IT / Security", "Qualified Individual", "Chicago", "named"],
];

export const SEATS: readonly Seat[] = ROWS.map(
  ([initials, name, role, title, office, flags], index) => ({
    n: index + 1,
    initials,
    name,
    role,
    title,
    office,
    named: flags === "named" || flags === "named-seasonal",
    seasonal: flags === "seasonal" || flags === "named-seasonal",
  }),
);

/** The persona slug a screen is seen as (`?as=hannah-leclerc`). */
export function slugOf(name: string): string {
  return name.toLowerCase().replace(/[^a-z]+/g, "-");
}

export function emailOf(name: string): string {
  const [first = "", ...rest] = name.toLowerCase().split(" ");
  return `${first}.${rest.join("")}@brightwaterhale.com`;
}

/** Seat holders who carry a firm-level role in `/v1/firm/staff` (identity `firm_role`). */
export const FIRM_ROLES: Readonly<
  Record<string, "firm_admin" | "practice_leader" | "quality_partner">
> = {
  GH: "firm_admin",
  FA: "firm_admin",
  MO: "practice_leader",
  TW: "quality_partner",
};

export const OFFICES: readonly {
  name: OfficeName;
  hq: boolean;
  address: string;
  seats: number;
  namedSeats: number;
}[] = [
  {
    name: "Chicago",
    hq: true,
    address: "311 West Brannock Street, Suite 1700, Chicago, IL 60606",
    seats: 22,
    namedSeats: 7,
  },
  {
    name: "Denver",
    hq: false,
    address: "1820 Coalbank Street, Suite 400, Denver, CO 80202",
    seats: 14,
    namedSeats: 4,
  },
  {
    name: "New York",
    hq: false,
    address: "60 Quillon Place, 23rd Floor, New York, NY 10006",
    seats: 10,
    namedSeats: 3,
  },
];

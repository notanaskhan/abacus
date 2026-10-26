// ADM-03's search params and the words it builds from data (G-01 §5.1). The URL carries the
// expanded office (by its code), the open overlay (a wall's log, or the new-wall sheet, which may
// name its person and client by id) and an anchor; never a name, an email or a TIN.

import type { FirmMemberOut, FirmTeamOut } from "@abacus/api-client";

export interface Adm03Search {
  /** The office code shown expanded ("CHI"). */
  expand?: string;
  /** `wall:<id>` (the log), `wall:new` or `wall:new:<userId>:<clientId>` (the sheet). */
  ov?: string;
}

export type Adm03Patch = { [K in keyof Adm03Search]?: Adm03Search[K] | undefined };

const KEYS = ["expand", "ov"] as const;

export function parseSearch(raw: Readonly<Record<string, unknown>> | string): Adm03Search {
  const source: Readonly<Record<string, unknown>> =
    typeof raw === "string"
      ? Object.fromEntries(new URLSearchParams(raw.split("#")[0] ?? ""))
      : raw;
  const out: Adm03Search = {};
  for (const key of KEYS) {
    const value = source[key];
    if (typeof value === "string" && value !== "") out[key] = value;
  }
  return out;
}

/** The anchor a `?…#walls` string carries ("walls", "offshore"), if any. */
export function anchorOf(raw: string): string | undefined {
  const hash = raw.split("#")[1];
  return hash === undefined || hash === "" ? undefined : hash;
}

export type Overlay =
  | { kind: "none" }
  | { kind: "log"; wallId: string }
  | { kind: "new"; userId?: string; clientId?: string };

export function overlayOf(ov: string | undefined): Overlay {
  if (ov === undefined || !ov.startsWith("wall:")) return { kind: "none" };
  const rest = ov.slice(5);
  if (rest === "new" || rest.startsWith("new:")) {
    const [, userId, clientId] = rest.split(":");
    return {
      kind: "new",
      ...(userId === undefined || userId === "" ? {} : { userId }),
      ...(clientId === undefined || clientId === "" ? {} : { clientId }),
    };
  }
  return rest === "" ? { kind: "none" } : { kind: "log", wallId: rest };
}

/** "MO" for Margaret Okonkwo. */
export function initialsOf(name: string): string {
  const words = name.trim().split(/\s+/);
  const first = words[0]?.[0] ?? "";
  const last = words.length > 1 ? (words[words.length - 1]?.[0] ?? "") : "";
  return `${first}${last}`.toUpperCase();
}

export type Names = ReadonlyMap<string, string>;

export function namesOf(members: readonly FirmMemberOut[]): Names {
  return new Map(members.map((m) => [m.user_id, m.display_name]));
}

/** A reviewer pool as the design draws it: its name, with its members' initials when the name
 * isn't already them ("Tax reviewers in Chicago (YK)", "IM, OB"). */
export function poolText(team: FirmTeamOut, names: Names): string {
  const initials = team.member_ids.map((id) => initialsOf(names.get(id) ?? "")).join(", ");
  return team.name === initials || initials === "" ? team.name : `${team.name} (${initials})`;
}

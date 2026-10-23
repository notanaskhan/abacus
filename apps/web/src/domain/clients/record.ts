// The client record (P-07 §5, L3; docs/contracts/clients.md): CLI-02's reads and writes over the
// generated client only. A walled or unknown client answers 404 (INV-3), which the screen draws
// as a record that cannot be opened, never as a hidden one. The overview is a list of sections
// that registered providers return, each already filtered by its own read action on the server:
// the screen draws what arrives and nothing for what does not (ADR-024).

import type {
  ClientEntityBriefOut,
  ClientOverviewItemOut,
  ClientOverviewOut,
  ClientOverviewSectionOut,
  ClientPatchIn,
  ClientRecordOut,
  MaskedTinOut,
  TinRevealIn,
} from "@abacus/api-client";
import {
  clientOverviewOptions,
  getClientOptions,
  getClientQueryKey,
  revealTinMutation,
  staffOptions,
  updateClientMutation,
} from "@abacus/api-client/query";
import { isoDate } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

export type RevealReason = TinRevealIn["reason"];

/** The reveal reason registry (DEC-141), in the order the dialog offers them. */
export const REVEAL_REASONS: readonly RevealReason[] = [
  "prepare_return",
  "review_return",
  "file_or_correct_filing",
  "respond_to_notice",
  "verify_identity",
];

export function useClientRecord(clientId: string) {
  return useQuery({ ...getClientOptions({ path: { client_id: clientId } }), retry: false });
}

export function useClientOverview(clientId: string) {
  return useQuery({ ...clientOverviewOptions({ path: { client_id: clientId } }), retry: false });
}

/** Staff names by user id, for the Team band's derived Manager and Preparer (DEC-62). */
export function useStaff(): { names: ReadonlyMap<string, string>; ids: readonly string[] } {
  const { data } = useQuery({ ...staffOptions(), retry: false });
  const members = (data?.members ?? []).filter((m) => m.status === "active");
  return {
    names: new Map(members.map((m) => [m.user_id, m.display_name])),
    ids: members.map((m) => m.user_id),
  };
}

/** PATCH with the version the person saw; a stale one is the server's 409, never a merge. */
export function useUpdateClient(clientId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    ...updateClientMutation(),
    onSuccess: (record) => {
      queryClient.setQueryData(getClientQueryKey({ path: { client_id: clientId } }), record);
    },
  });
}

export function patchOf(record: ClientRecordOut, change: Omit<ClientPatchIn, "seen_version">) {
  return {
    path: { client_id: record.id },
    body: { ...change, seen_version: record.version },
  };
}

/** The reveal: a person's act with a reason; the plain value lives only in the caller's state. */
export function useRevealTin() {
  return useMutation({ ...revealTinMutation() });
}

// ---- reading the overview -----------------------------------------------------------------------

export function sectionOf(
  overview: ClientOverviewOut | undefined,
  code: string,
): ClientOverviewSectionOut | undefined {
  return overview?.sections.find((s) => s.code === code);
}

export function itemOf(
  section: ClientOverviewSectionOut | undefined,
  key: string,
): ClientOverviewItemOut | undefined {
  return section?.items.find((i) => i.key === key);
}

/** The items of a stats section with their `<key>.of` denominators folded in. */
export interface StatItem {
  item: ClientOverviewItemOut;
  of: string | null;
}

export function statItems(section: ClientOverviewSectionOut | undefined): StatItem[] {
  const items = section?.items ?? [];
  return items
    .filter((i) => !i.key.endsWith(".of"))
    .map((item) => ({ item, of: itemOf(section, `${item.key}.of`)?.figure ?? null }));
}

/** The entity whose taxpayer id the Details band shows: the first one with a TIN on file. */
export function tinEntity(record: ClientRecordOut): ClientEntityBriefOut | undefined {
  return record.entities.find((e) => e.tin != null);
}

/** "XX-XXX0287" for an EIN, "•••-••-2208" for an SSN or ITIN; null while applied for. */
export function maskTin(tin: MaskedTinOut): string | null {
  if (tin.presence !== "on_file" || tin.last4 == null) return null;
  return tin.kind === "ein" ? `XX-XXX${tin.last4}` : `•••-••-${tin.last4}`;
}

/** The first word of an individual entity's name ("Claire Feld" → "Claire"). */
export function givenName(entity: ClientEntityBriefOut): string {
  return entity.name.split(/\s+/)[0] ?? entity.name;
}

/** Whole days from `now` to a calendar date in the firm's zone, never below zero. */
export function daysUntil(on: string, now: Date, tz: string): number {
  const today = isoDate(now, tz);
  const ms = Date.parse(`${on}T00:00:00Z`) - Date.parse(`${today}T00:00:00Z`);
  return Math.max(0, Math.round(ms / 86_400_000));
}

/** Sum of decimal strings as an integer-cents bigint, then back to a decimal string (ADR-050). */
export function sumFigures(figures: readonly string[]): string {
  let cents = 0n;
  for (const f of figures) {
    const [whole = "0", frac = ""] = f.split(".");
    const sign = whole.startsWith("-") ? -1n : 1n;
    const digits = whole.replace("-", "");
    cents +=
      sign * (BigInt(digits === "" ? "0" : digits) * 100n + BigInt((frac + "00").slice(0, 2)));
  }
  const neg = cents < 0n;
  const abs = neg ? -cents : cents;
  const whole = (abs / 100n).toString();
  const rest = abs % 100n;
  const text = rest === 0n ? whole : `${whole}.${rest.toString().padStart(2, "0")}`;
  return neg ? `-${text}` : text;
}

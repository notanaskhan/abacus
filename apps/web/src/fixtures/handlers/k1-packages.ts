// Fixture handlers for TXP-12's K-1 routes (T-02-T25; docs/contracts/k1-packages.md), over the
// seed in seed/k1-packages.ts. Each write answers as the live route does: the share returns how
// many hand-offs it made, the release a pending release whose Undo window closes ten seconds on,
// Undo the release undone, Resend the package. The screen refetches its reads after each.
import type {
  K1PackageDetailOut,
  K1PackageOut,
  K1ReleaseOut,
  TaxReturnRecordOut,
} from "@abacus/api-client";
import { nowMs } from "../../app-core/clock";
import { type FixtureHandler, json } from "../../app-core/fixture-mode";
import {
  BLUESTEM_RETURN,
  CALLOWAY_RETURN,
  type K1Variant,
  RIDGELINE_RETURN,
  k1Check,
  k1Counts,
  k1Lines,
  k1Rows,
  k1Tin,
} from "../seed/k1-packages";
import { stableId } from "../seed/prng";

function find(variant: K1Variant, id: string): K1PackageOut | undefined {
  return [RIDGELINE_RETURN, BLUESTEM_RETURN, CALLOWAY_RETURN]
    .flatMap((r) => k1Rows(r, variant))
    .find((r) => r.id === id);
}

/** The return's record as TXP-12's subbar reads it: Ridgeline is filed once approved (A5, B). */
export function k1Record(record: TaxReturnRecordOut, variant: K1Variant): TaxReturnRecordOut {
  if (record.row.id !== RIDGELINE_RETURN || variant === "drafts") return record;
  return { ...record, row: { ...record.row, status: "filed" } };
}

export function k1PackageHandlers(
  variant: K1Variant,
  base: Readonly<Record<string, FixtureHandler>>,
): Record<string, FixtureHandler> {
  const record = base["GET /v1/tax-returns/{return_id}"];
  return {
    ...(record === undefined
      ? {}
      : {
          "GET /v1/tax-returns/{return_id}": async (request) => {
            const answered = await record(request);
            if (!answered.ok) return answered;
            return json(k1Record((await answered.json()) as TaxReturnRecordOut, variant));
          },
        }),
    "GET /v1/tax-returns/{return_id}/k1-packages": ({ params }) => {
      const rows = k1Rows(params.return_id ?? "", variant);
      return json({ items: rows, next_cursor: null, total: rows.length, counts: k1Counts(rows) });
    },
    "GET /v1/tax-returns/{return_id}/k1-packages/release-check": ({ params }) =>
      json(k1Check(params.return_id ?? "", variant)),
    "GET /v1/k1-packages/{package_id}": ({ params }) => {
      const pkg = find(variant, params.package_id ?? "");
      if (pkg === undefined) return json({ detail: "not_found" }, 404);
      const detail: K1PackageDetailOut = {
        package: pkg,
        lines: k1Lines(pkg),
        documents: pkg.documents ?? [],
        tin: k1Tin(pkg.id),
      };
      return json(detail);
    },
    "POST /v1/tax-returns/{return_id}/k1-packages:share-internal": ({ body }) => {
      const b = body as { package_ids: string[]; target_return_ids: string[] };
      return json({ shared: b.package_ids.length * b.target_return_ids.length });
    },
    "POST /v1/tax-returns/{return_id}/k1-packages:release": ({ params }) => {
      const out: K1ReleaseOut = {
        release_id: stableId(`k1-release:${params.return_id ?? ""}`),
        status: "pending",
        not_before: new Date(nowMs() + 10_000).toISOString(),
      };
      return json(out, 202);
    },
    "POST /v1/k1-releases/{release_id}:undo": ({ params }) => {
      const out: K1ReleaseOut = {
        release_id: params.release_id ?? "",
        status: "undone",
        not_before: new Date(nowMs()).toISOString(),
      };
      return json(out);
    },
    "POST /v1/k1-packages/{package_id}:resend": ({ params }) => {
      const pkg = find(variant, params.package_id ?? "");
      return pkg === undefined ? json({ detail: "not_found" }, 404) : json(pkg);
    },
    "GET /v1/k1-recipients/{recipient_id}/details-changes": () => json([]),
  };
}

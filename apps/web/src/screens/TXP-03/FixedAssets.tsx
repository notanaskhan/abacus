// TXP-03 on the live client (T-06-T29): the register for the view (`GET …/fixed-assets`), the
// section's sign-off through POST …/sections/fixed-assets/sign-off with the hash the viewer saw,
// and an asset change as a C3 proposal (POST …/fixed-assets/{id}/changes; applied only on a
// reviewer's approval). The view and the open asset start from the URL (`?view=`, `?asset=`).
import {
  entitySectionSignOffMutation,
  entitySectionsOptions,
  fixedAssetChangeMutation,
  fixedAssetsOptions,
} from "@abacus/api-client/query";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { type JSX, useState } from "react";
import { useSession } from "../../app-core/session";
import { to } from "../../routes/to";
import { TXP03, type Txp03View } from "./index";

const SECTION = "fixed-assets";
const VIEWS: readonly Txp03View[] = ["register", "by_property", "dispositions"];

function initialsOf(name: string): string {
  return name
    .split(/\s+/)
    .filter((w) => w.length > 0)
    .map((w) => w.charAt(0).toUpperCase())
    .slice(0, 2)
    .join("");
}

export function FixedAssets({
  returnId,
  search,
  onOpenDocument,
}: {
  returnId: string;
  /** The opening search (`?view=…&asset=…`); default: the page's own. */
  search?: string;
  /** SHL-08 on the open asset's evidence (the shell's overlay wiring). */
  onOpenDocument?: (assetId: string) => void;
}): JSX.Element {
  const initial = new URLSearchParams(
    search ?? (typeof window === "undefined" ? "" : window.location.search),
  );
  const asked = initial.get("view") as Txp03View | null;
  const [view, setView] = useState<Txp03View>(
    asked !== null && VIEWS.includes(asked) ? asked : "register",
  );
  const [assetId, setAssetId] = useState<string | null>(initial.get("asset"));
  const [signOffOpen, setSignOffOpen] = useState(false);
  const path = { return_id: returnId };
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const session = useSession();
  const fa = useQuery(fixedAssetsOptions({ path, query: { view } }));
  const sections = useQuery(entitySectionsOptions({ path }));
  const section = sections.data?.items.find((s) => s.key === SECTION);
  const signOff = useMutation({
    ...entitySectionSignOffMutation(),
    onSuccess: () => {
      setSignOffOpen(false);
      void queryClient.invalidateQueries({ queryKey: entitySectionsOptions({ path }).queryKey });
    },
  });
  const propose = useMutation(fixedAssetChangeMutation());
  const signed = (section?.signed_levels.length ?? 0) > 0;
  const name = session.user?.displayName;
  return (
    <TXP03
      fixedAssets={fa.data}
      view={view}
      assetId={assetId}
      signOffOpen={signOffOpen}
      signedBy={signed && name !== undefined ? initialsOf(name) : undefined}
      onView={setView}
      onAsset={setAssetId}
      {...(assetId === null || onOpenDocument === undefined
        ? {}
        : {
            onOpenInvoice: () => {
              onOpenDocument(assetId);
            },
          })}
      onPropose={(id, change) => {
        propose.mutate({
          path: { ...path, asset_id: id },
          headers: { "Idempotency-Key": crypto.randomUUID() },
          body: { ...change, expected_version: 1 },
        });
      }}
      // DV-3: PRJ-01 is fixture-only until T-09; the issue queue is TXP-10.
      onOpenProject={() => void navigate(to.TXP10({ returnId }))}
      onSignOffOpen={setSignOffOpen}
      // Fail closed: without the section's hash nothing is posted.
      {...(section?.seen_hash === undefined
        ? {}
        : {
            onSignOff: (note: string | null) => {
              signOff.mutate({
                path: { ...path, key: SECTION },
                headers: { "Idempotency-Key": crypto.randomUUID() },
                body: { level: "l2", seen_hash: section.seen_hash ?? "", note },
              });
            },
          })}
    />
  );
}

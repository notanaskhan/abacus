// TXP-07 on the live client (T-05-T68; docs/screens/TXP-07.md): the capital accounts for the
// view, the partners for the pane headers, Computing while a workbook run is running, and the
// section's sign-off through POST …/sections/capital-accounts/sign-off with the hash the viewer
// saw. An off tie-out opens the blocked explanation (b2) first; the screen sums nothing.
import {
  entityCapitalAccountsOptions,
  entityPartnersOptions,
  entityRunsOptions,
  entitySectionSignOffMutation,
  entitySectionsOptions,
} from "@abacus/api-client/query";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { useSession } from "../../app-core/session";
import { to } from "../../routes/to";
import { TXP07, type Txp07View } from "./index";

const SECTION = "capital-accounts";

function initialsOf(name: string): string {
  return name
    .split(/\s+/)
    .filter((w) => w.length > 0)
    .map((w) => w.charAt(0).toUpperCase())
    .slice(0, 2)
    .join("");
}

export function CapitalAccounts({
  returnId,
  onOpenCell,
}: {
  returnId: string;
  /** SHL-09 on an amber cell (the shell's overlay wiring). */
  onOpenCell?: (cell: string) => void;
}): JSX.Element {
  const [view, setView] = useState<Txp07View>("by_partner");
  const [page, setPage] = useState(0);
  const [signOffOpen, setSignOffOpen] = useState(false);
  const path = { return_id: returnId };
  const queryClient = useQueryClient();
  const session = useSession();
  const navigate = useNavigate();
  const capital = useQuery(entityCapitalAccountsOptions({ path }));
  const partners = useQuery(entityPartnersOptions({ path }));
  const runs = useQuery(entityRunsOptions({ path }));
  const sections = useQuery(entitySectionsOptions({ path }));
  const section = sections.data?.items.find((s) => s.key === SECTION);
  const signOff = useMutation({
    ...entitySectionSignOffMutation(),
    onSuccess: () => {
      setSignOffOpen(false);
      void queryClient.invalidateQueries({ queryKey: entitySectionsOptions({ path }).queryKey });
    },
  });
  const signed = (section?.signed_levels.length ?? 0) > 0;
  const name = session.user?.displayName;
  return (
    <TXP07
      capital={capital.data}
      partners={partners.data}
      view={view}
      page={page}
      computing={runs.data?.items[0]?.state === "running"}
      signOffOpen={signOffOpen}
      signedBy={signed && name !== undefined ? initialsOf(name) : undefined}
      onView={setView}
      onPage={setPage}
      {...(onOpenCell === undefined ? {} : { onOpenCell })}
      // T-05-T69: typed links (link contract rule 1): the M-2 review point and the transfers.
      onOpenIssue={() => void navigate(to.TXP10({ returnId }))}
      onTransfers={() =>
        void navigate({
          ...to.TXP06({ returnId, section: "schedule-k" }),
          search: { ov: "allocation" },
        })
      }
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

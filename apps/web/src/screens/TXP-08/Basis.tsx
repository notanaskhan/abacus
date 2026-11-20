// TXP-08 on the live client (T-06-T31): the basis for the view and partner (`GET …/basis`), the
// return's partners for the picker, and the §754 waiting-on-client issue Send to client… shows
// (TXP-10's queue: the waiting item on 04 Partner Txns), never a new request. The view, the
// partner and the inline card start from the URL (`?view=s752`, `?partner=`, `?card=754`).
import {
  basisOptions,
  entityIssuesOptions,
  entityPartnersOptions,
} from "@abacus/api-client/query";
import { useQuery } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { TXP08, type Txp08View } from "./index";

const PARTNER_TXNS = "04 Partner Txns";

export function Basis({
  returnId,
  search,
  onOpen,
}: {
  returnId: string;
  /** The opening search; default: the page's own. */
  search?: string;
  /** Open an entity section by its path suffix ("/issues"). */
  onOpen?: (suffix: string) => void;
}): JSX.Element {
  const initial = new URLSearchParams(
    search ?? (typeof window === "undefined" ? "" : window.location.search),
  );
  const [view, setView] = useState<Txp08View>(initial.get("view") === "s752" ? "s752" : "basis");
  const [partnerId, setPartnerId] = useState<string | null>(initial.get("partner"));
  const [cardOpen, setCardOpen] = useState(initial.get("card") === "754");
  const path = { return_id: returnId };
  const basis = useQuery(
    basisOptions({ path, query: { view, ...(partnerId === null ? {} : { partner: partnerId }) } }),
  );
  const partners = useQuery(entityPartnersOptions({ path }));
  const issues = useQuery(entityIssuesOptions({ path }));
  const waiting = issues.data?.items.find(
    (i) =>
      i.section === "waiting_on_client" && (i.cells ?? []).some((c) => c.sheet === PARTNER_TXNS),
  );
  return (
    <TXP08
      basis={basis.data}
      partners={(partners.data?.partners ?? []).map((p) => ({ id: p.id, name: p.name }))}
      view={view}
      partnerId={partnerId}
      cardOpen={cardOpen}
      waitingIssue={
        waiting === undefined ? undefined : { title: waiting.title, step: waiting.step ?? "" }
      }
      // DV-3: PRJ-01 is T-09's; until then the link is drawn in fixture builds only.
      requestMore={import.meta.env.VITE_FIXTURES === "1" ? "fixture" : "hidden"}
      onView={setView}
      onPartner={setPartnerId}
      onCard={setCardOpen}
      onOpenIssue={() => onOpen?.("/issues")}
      onRequestMore={() => undefined}
    />
  );
}

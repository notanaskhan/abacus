// TXP-09 on the live client (T-06-T32): the return's states (`GET …/states`). The view starts from
// the URL (`?view=credits|nexus`). "Approve sourcing…" opens SHL-10 over the review point; the NYC
// Recommend row opens TAX-15 pre-filled; a credit row opens TXP-12's state K-1 column.
import { statesOptions } from "@abacus/api-client/query";
import { useQuery } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { TXP09, type Txp09View } from "./index";

const VIEWS: readonly Txp09View[] = ["apportionment", "credits", "nexus"];

export function States({
  returnId,
  search,
  onOpen,
}: {
  returnId: string;
  search?: string;
  onOpen?: (suffix: string) => void;
}): JSX.Element {
  const initial = new URLSearchParams(
    search ?? (typeof window === "undefined" ? "" : window.location.search),
  );
  const asked = initial.get("view") as Txp09View | null;
  const [view, setView] = useState<Txp09View>(
    asked !== null && VIEWS.includes(asked) ? asked : "apportionment",
  );
  const states = useQuery(statesOptions({ path: { return_id: returnId }, query: { view } }));
  return (
    <TXP09
      states={states.data}
      view={view}
      onView={setView}
      onApproveSourcing={() => onOpen?.("/issues")}
      onMap={() => onOpen?.("/review/fixed-assets")}
      onRecommend={() => onOpen?.("/planning")}
      onCredits={() => onOpen?.("/k1")}
    />
  );
}

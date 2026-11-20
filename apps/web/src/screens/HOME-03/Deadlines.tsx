// HOME-03 on the live client (T-08-T16): the filing deadlines (`GET /v1/filing-deadlines?view=`),
// the view and person from the URL, chips routed by source kind (the host navigates).
import { filingDeadlinesOptions } from "@abacus/api-client/query";
import { useQuery } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { type ChipTarget, HOME03, type Home03View } from "./index";

export function Deadlines({
  onOpen,
}: {
  onOpen?: (workItemId: string | null, target: ChipTarget) => void;
}): JSX.Element {
  const initial = new URLSearchParams(typeof window === "undefined" ? "" : window.location.search);
  const asked = initial.get("view");
  const [view, setView] = useState<Home03View>(
    asked === "week" || asked === "list" ? asked : "month",
  );
  // The month shown and its grid's edges (Sunday before the 1st to Saturday after the last day).
  const [month] = useState(() => {
    const now = new Date();
    return { y: now.getFullYear(), m: now.getMonth() };
  });
  const first = new Date(Date.UTC(month.y, month.m, 1));
  const last = new Date(Date.UTC(month.y, month.m + 1, 0));
  const from = new Date(first.getTime() - first.getUTCDay() * 86_400_000)
    .toISOString()
    .slice(0, 10);
  const to = new Date(last.getTime() + (6 - last.getUTCDay()) * 86_400_000)
    .toISOString()
    .slice(0, 10);
  const data = useQuery(filingDeadlinesOptions({ query: { view, from, to } }));
  return (
    <HOME03
      calendar={data.data}
      view={view}
      onView={setView}
      onOpen={(item, target) => onOpen?.(item.work_item_id ?? null, target)}
    />
  );
}

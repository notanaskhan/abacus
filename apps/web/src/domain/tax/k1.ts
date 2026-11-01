// The issuing return of a draft K-1 shared to a return (T-02-T25): TAX-01's Draft K-1 popover and
// TAX-09's blocked line link to that return's K-1 package (TXP-12). The source comes from the
// return's overview (`k1_dependencies`), named only to a reader of both returns (DEC-88); with
// no readable source there is no link.
import { returnOverviewOptions } from "@abacus/api-client/query";
import { useQuery } from "@tanstack/react-query";

export function useDraftK1Source(returnId: string, enabled = true): string | null {
  const overview = useQuery({
    ...returnOverviewOptions({ path: { return_id: returnId } }),
    enabled,
  });
  const dep = (overview.data?.k1_dependencies ?? []).find(
    (d) => d.blocking === true && d.source_return_id !== null,
  );
  return dep?.source_return_id ?? null;
}

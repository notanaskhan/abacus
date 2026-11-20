// ENG-07's page (T-08-T15): the newest season's manifest, by the seasons list.
import { seasonsOptions } from "@abacus/api-client/query";
import { EmptyState } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import type { JSX } from "react";
import { Season } from "./Season";

export function SeasonPage(): JSX.Element {
  const seasons = useQuery(seasonsOptions());
  const newest = seasons.data?.items.find((s) => s.manifest_id != null);
  if (newest?.manifest_id == null) {
    return <EmptyState title="No season manifest yet" icon="clock" />;
  }
  return <Season taxYear={newest.tax_year} manifestId={newest.manifest_id} />;
}

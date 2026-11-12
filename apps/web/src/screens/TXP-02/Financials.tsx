// TXP-02 on the live client (T-05-T37): the trial balance and its tallies for the view and the
// statement, Building while a workbook run imports the trial balance (the newest run running).
import {
  entityRunsOptions,
  entityTalliesOptions,
  entityTrialBalanceOptions,
} from "@abacus/api-client/query";
import { useQuery } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { TXP02, type Txp02Statement, type Txp02View } from "./index";

export function Financials({
  returnId,
  onOpenCell,
}: {
  returnId: string;
  /** SHL-09 on an account's row (T-05-T38 wires the overlay). */
  onOpenCell?: (accountCode: string) => void;
}): JSX.Element {
  const [view, setView] = useState<Txp02View>("account");
  const [statement, setStatement] = useState<Txp02Statement>("full");
  const [unmappedOnly, setUnmappedOnly] = useState(false);
  const path = { return_id: returnId };
  const tb = useQuery(
    entityTrialBalanceOptions({
      path,
      query: { view, statement, ...(unmappedOnly ? { filter: "unmapped" as const } : {}) },
    }),
  );
  const tallies = useQuery(entityTalliesOptions({ path }));
  const runs = useQuery(entityRunsOptions({ path }));
  const building = runs.data?.items[0]?.state === "running";
  return (
    <TXP02
      tb={tb.data}
      tallies={tallies.data}
      view={view}
      statement={statement}
      building={building}
      onView={setView}
      onStatement={setStatement}
      onUnmapped={() => {
        setUnmappedOnly((on) => !on);
      }}
      {...(onOpenCell === undefined ? {} : { onOpenRow: onOpenCell })}
    />
  );
}

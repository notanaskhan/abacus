// TXP-05 on the live client (T-05-T43): Schedule K for the view, the partners (Item J and the
// columns), the capital accounts (Item L) and the allocation structure (the card); Building while
// a workbook run is running; line 2's Form 8825 breakdown on demand.
import {
  entityAllocationOptions,
  entityCapitalAccountsOptions,
  entityPartnersOptions,
  entityRunsOptions,
  entityScheduleKBreakdownOptions,
  entityScheduleKOptions,
} from "@abacus/api-client/query";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { type JSX, useState } from "react";
import { to } from "../../routes/to";
import { Allocation } from "../TXP-06/Allocation";
import { TXP05, type Txp05View } from "./index";

export function ScheduleK({
  returnId,
  onOpen,
  onOpenCell,
}: {
  returnId: string;
  /** Open an entity section by its path suffix ("/issues"). */
  onOpen?: (suffix: string) => void;
  /** SHL-09 on a line's cells (the shell's overlay wiring). */
  onOpenCell?: (line: string) => void;
}): JSX.Element {
  const navigate = useNavigate();
  const [view, setView] = useState<Txp05View>("federal");
  const [line, setLine] = useState<string | null>(null);
  const [itemLOpen, setItemLOpen] = useState(false);
  // `?ov=allocation` (TXP-06 over this tab): Esc and X return here.
  const [allocationOpen, setAllocationOpen] = useState(
    typeof window !== "undefined" &&
      new URLSearchParams(window.location.search).get("ov") === "allocation",
  );
  const path = { return_id: returnId };
  const k = useQuery(entityScheduleKOptions({ path, query: { view } }));
  const partners = useQuery(entityPartnersOptions({ path }));
  const capital = useQuery(entityCapitalAccountsOptions({ path }));
  const allocation = useQuery(entityAllocationOptions({ path }));
  const runs = useQuery(entityRunsOptions({ path }));
  const breakdown = useQuery({
    ...entityScheduleKBreakdownOptions({ path: { ...path, line: line ?? "2" } }),
    enabled: line === "2",
  });
  return (
    <>
      {allocationOpen ? (
        <Allocation
          returnId={returnId}
          onClose={() => {
            setAllocationOpen(false);
          }}
          onItemL={() => void navigate(to.TXP07({ returnId, section: "capital-accounts" }))}
        />
      ) : null}
      <TXP05
        k={k.data}
        partners={partners.data}
        capital={capital.data}
        allocation={allocation.data}
        view={view}
        building={runs.data?.items[0]?.state === "running"}
        breakdown={line === "2" ? breakdown.data : undefined}
        itemLOpen={itemLOpen}
        onView={setView}
        onAllocation={() => {
          setAllocationOpen(true);
        }}
        onOpenLine={(next) => {
          if (next === "2") setLine("2");
          else onOpenCell?.(next);
        }}
        onCloseBreakdown={() => {
          setLine(null);
        }}
        onItemL={setItemLOpen}
        // TXP-07 is routed (T-05-T55): a typed link (link contract rule 1).
        onOpenCapital={() => void navigate(to.TXP07({ returnId, section: "capital-accounts" }))}
        onOpenIssues={() => onOpen?.("/issues")}
        // A5: a partner header opens the K-1 package (TXP-12; TAX-11 is planned).
        onPartner={() => void navigate(to.TXP12({ returnId }))}
      />
    </>
  );
}

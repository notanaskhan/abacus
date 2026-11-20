// TXP-04 on the live client (T-06-T30): Schedule M-3 and the M-1 reference (`GET …/schedules/m3`,
// `…/m1`), and T-05's M-2 as drafted and with the proposed fix (`…/schedules/m2?variant=`). The
// fix is the M-2 issue's proposal (TXP-10's fix run on 07 M-2): Accept… opens SHL-10's ApproveSheet
// on it and never applies the value here; Reject… posts the reason. With no open proposal and M-2
// tying, the fix is the workbook's (d). The frame is the tab; the toggle and variant start from
// the URL (`?m1=1`, `?variant=with_fix`).
import {
  entityIssuesOptions,
  entityM2Options,
  issueOptions,
  m1Options,
  m3Options,
  proposalRejectMutation,
} from "@abacus/api-client/query";
import { useMutation, useQuery } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { ApproveSheet } from "../SHL-10";
import { type M2Variant, TXP04, type Txp04Frame } from "./index";

const M2_SHEET = "07 M-2";

export function BookTax({
  returnId,
  frame,
  search,
  onOpen,
}: {
  returnId: string;
  frame: Txp04Frame;
  /** Open an entity section by its path suffix ("/activity"). */
  onOpen?: (suffix: string) => void;
  /** The opening search; default: the page's own. */
  search?: string;
}): JSX.Element {
  const initial = new URLSearchParams(
    search ?? (typeof window === "undefined" ? "" : window.location.search),
  );
  const [showM1, setShowM1] = useState(initial.get("m1") === "1");
  const [variant, setVariant] = useState<M2Variant>(
    initial.get("variant") === "with_fix" ? "with_fix" : "as_drafted",
  );
  const [approving, setApproving] = useState(false);
  const path = { return_id: returnId };
  const m2 = frame === "schedule-m2";
  const m3 = useQuery({ ...m3Options({ path }), enabled: !m2 });
  const m1 = useQuery({ ...m1Options({ path }), enabled: !m2 && showM1 });
  const shown = useQuery({ ...entityM2Options({ path, query: { variant } }), enabled: m2 });
  const fix = useQuery({
    ...entityM2Options({ path, query: { variant: "with_fix" } }),
    enabled: m2,
  });
  const issues = useQuery({ ...entityIssuesOptions({ path }), enabled: m2 });
  const m2Issue = issues.data?.items.find((i) =>
    (i.cells ?? []).some((c) => c.sheet === M2_SHEET),
  );
  const detail = useQuery({
    ...issueOptions({ path: { issue_id: m2Issue?.id ?? "" } }),
    enabled: m2 && m2Issue !== undefined,
  });
  const proposalRef = detail.data?.fix_run?.proposal_id ?? null;
  const reject = useMutation(proposalRejectMutation());
  const accepted =
    proposalRef === null && shown.data?.variant === "as_drafted" && shown.data.tie === "tie";
  const line4 = fix.data?.lines?.find((l) => l.line === 4)?.amount;
  return (
    <>
      {approving && proposalRef !== null ? (
        <ApproveSheet proposalRef={proposalRef} open onOpenChange={setApproving} />
      ) : null}
      <TXP04
        frame={frame}
        m3={m3.data}
        m1={m1.data}
        showM1={showM1}
        m2={shown.data}
        proposedLine4={line4}
        variant={variant}
        accepted={accepted}
        canDecide={proposalRef !== null}
        onShowM1={setShowM1}
        onVariant={setVariant}
        onAccept={() => {
          setApproving(true);
        }}
        onReject={(reason) => {
          if (proposalRef === null) return;
          reject.mutate({
            path: { proposal_id: proposalRef },
            body: { reason_code: reason, seen_version: 1, note: null },
          });
        }}
        // The checkpoint opens in SHL-16 over TAX-07 (the return's Activity).
        onOpenCheckpoint={() => onOpen?.("/activity")}
      />
    </>
  );
}

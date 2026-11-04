import { type JSX, useState } from "react";
import { useOpenOverlay } from "../../app-core/open";
import { ov } from "../../routes/to";
import { type MisstatementView, MisstatementsWorkbook } from "./Workbook";

// AUD-16's public entry (A-06-T22): the Misstatements tab's workbook under the Evaluation chrome,
// with its overlays: Send to client… (`?ov=send-entries:<entryId>…`), the `sum_conclusion` card
// (`?ov=decision:<cardId>`) and Sign off… on the SUM schedule (`?ov=signoff:sum_schedule:<wi>:L2`).

export { type MisstatementView, MisstatementsWorkbook } from "./Workbook";
export { SendEntriesBody, SendEntriesSheet } from "./SendEntries";

export function MisstatementsPane({
  auditId,
  initialView = "passed",
  onFinding,
}: {
  auditId: string;
  initialView?: MisstatementView;
  onFinding?: (ref: string) => void;
}): JSX.Element {
  const [view, setView] = useState<MisstatementView>(initialView);
  const open = useOpenOverlay();
  return (
    <MisstatementsWorkbook
      auditId={auditId}
      view={view}
      onView={setView}
      {...(onFinding === undefined ? {} : { onFinding })}
      onSend={(ids) => {
        open({ key: "send-entries", args: [...ids] });
      }}
      onDecision={(cardId) => {
        open(ov.SHL11(cardId));
      }}
      onSignOff={() => {
        open(ov.SHL12("sum_schedule", auditId, "L2"));
      }}
    />
  );
}

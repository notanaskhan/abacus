// SHL-20's fixture artboards (P-06-T22): `/components/screens/SHL-20?st=a…f`, each the frame on
// its scenario's data, opened as the artboard opens (b with the draft, f with "Why?").
import type { JSX } from "react";
import { EvidenceScreening } from "./index";
import { OPENS, type Shl20State } from "./scenarios";

export function SHL20({ state }: { state: Shl20State }): JSX.Element {
  const o = OPENS[state];
  return (
    <div data-state={state} className="min-h-[880px] bg-shell">
      <EvidenceScreening
        subject={o.subject}
        {...(o.file === undefined ? {} : { file: o.file })}
        {...(o.open === undefined ? {} : { open: o.open })}
      />
    </div>
  );
}

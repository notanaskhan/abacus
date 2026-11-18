// C-01-T43 (live swap 2): the C-20 frame a closes screen shows for a refused or failed read, the
// same frame live swap 1 drew inline on CLS-03 and CLS-09. A 403 is the role's restricted notice,
// a 404 a closed record (never revealed, INV-3), anything else the error with Retry. No record data
// renders inside it.
import { ViewStateBody } from "@abacus/ui";
import type { JSX } from "react";
import { closeReadState } from "./states";

type Read = Parameters<typeof closeReadState>[0];

/** The frame for `read` when it was refused or failed, else null (the screen renders itself). */
export function closeReadFrame(screen: string, read: Read): JSX.Element | null {
  const state = closeReadState(read);
  if (state.kind !== "restricted" && state.kind !== "error") return null;
  return (
    <div
      data-screen-body={screen}
      data-state={state.kind}
      className="flex min-h-0 flex-1 flex-col"
    >
      <ViewStateBody state={state} empty={{ title: "" }}>
        {null}
      </ViewStateBody>
    </div>
  );
}

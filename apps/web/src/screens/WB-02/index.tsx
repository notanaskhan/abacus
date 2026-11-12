// WB-02 New session & context picker (W-02-T08 skeleton; docs/screens/WB-02.md; SPEC-653). The
// blank, firm-wide session with the suggested prompts; picking one fills the composer and sends
// nothing (AC-C2). The picker, the context stack and the grounded answer are W-02-T16's.
import { EmptySession, WorkbenchLayout } from "@abacus/ui";
import type { JSX, ReactNode } from "react";
import { COPY, SUGGESTED_PROMPTS } from "./copy";

export interface WB02Props {
  /** The session list beside the thread (WB-01's, with the new row on top). */
  list: ReactNode;
  /** A suggested prompt's text goes to the composer; nothing is sent. */
  onDraft: (text: string) => void;
}

export function WB02({ list, onDraft }: WB02Props): JSX.Element {
  return (
    <WorkbenchLayout
      tab="sessions"
      list={list}
      chat={
        <EmptySession
          title={COPY.title}
          body={COPY.body}
          prompts={SUGGESTED_PROMPTS}
          onPick={(text) => {
            onDraft(text);
          }}
        />
      }
    />
  );
}

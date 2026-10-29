import { type Actor, toast } from "@abacus/ui";
import { type JSX, useState } from "react";
import { useSession } from "../../app-core/session";
import { TRIAGE_COPY as COPY, TriageSheet } from "../../domain/inbox";

// INB-02 · Attachment triage & File-to (N-01-T15; docs/screens/INB-02.md; DEC-1062): the O3 sheet
// over INB-01 (`/inbox?thread=…&ov=file&message=…`). Apply's answer closes it onto INB-01 with the
// toast "Filed 1 · Ignored 1 · Kevin Osei notified" (f).

export interface INB02Props {
  messageId: string | null;
  subject: string;
  sender: string;
  onClose: () => void;
  startDirty?: boolean;
}

export function INB02({
  messageId,
  subject,
  sender,
  onClose,
  startDirty = false,
}: INB02Props): JSX.Element {
  const session = useSession();
  const viewer: Actor =
    session.user === null ? { kind: "system" } : { kind: "human", name: session.user.displayName };
  const [open, setOpen] = useState(messageId);
  return (
    <TriageSheet
      messageId={open}
      subject={subject}
      sender={sender}
      viewer={viewer}
      startDirty={startDirty}
      onClose={() => {
        setOpen(null);
        onClose();
      }}
      onApplied={(result, notified) => {
        toast.show({
          kind: "success",
          text: COPY.toast(result.filed, result.ignored, result.held, notified),
        });
        setOpen(null);
        onClose();
      }}
    />
  );
}

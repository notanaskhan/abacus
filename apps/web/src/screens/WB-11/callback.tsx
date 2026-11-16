import { connectCompleteMutation } from "@abacus/api-client/query";
import { Spinner, toast } from "@abacus/ui";
import { useMutation } from "@tanstack/react-query";
import { type JSX, useEffect, useRef } from "react";

// W-01-T17 (WB-10, WB-11): the provider's return. The state and code are posted once (a reload
// never replays them: the server's state is single use), then the person is back on WB-10 with
// the outcome as a toast; the code never leaves this request.

const CONNECTED = "Connected.";
const FAILED = "That didn't connect. Try again.";

function detailOf(error: unknown): string {
  if (typeof error === "object" && error !== null && "detail" in error) {
    const detail = error.detail;
    if (typeof detail === "string") return detail;
  }
  return "connect_failed";
}

export function ConnectCallback({
  state,
  code,
  reasons,
  onDone,
}: {
  state: string;
  code: string;
  reasons: Readonly<Record<string, string>>;
  onDone: () => void;
}): JSX.Element {
  const sent = useRef(false);
  const complete = useMutation({
    ...connectCompleteMutation(),
    onSuccess: () => {
      toast.show({ kind: "success", text: CONNECTED });
      onDone();
    },
    onError: (error) => {
      toast.show({ kind: "error", text: reasons[detailOf(error)] ?? FAILED });
      onDone();
    },
  });
  useEffect(() => {
    if (sent.current) return;
    sent.current = true;
    if (state.length < 16 || code === "") {
      toast.show({ kind: "error", text: reasons.invalid_state ?? FAILED });
      onDone();
      return;
    }
    complete.mutate({
      body: { state, code },
      headers: { "Idempotency-Key": crypto.randomUUID() },
    });
  }, [state, code, complete, reasons, onDone]);
  return (
    <div data-screen="WB-11" data-callback className="flex flex-1 items-center justify-center">
      <Spinner label="Connecting…" />
    </div>
  );
}

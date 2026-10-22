import { complete } from "@abacus/api-client";
import { Alert, Spinner } from "@abacus/ui";
import { Link, useLocation, useNavigate } from "@tanstack/react-router";
import { type JSX, useEffect, useRef, useState } from "react";
import { errorMessage } from "../api";
import { accessToken, signIn } from "../auth/session";

const REASONS: Record<string, string> = {
  invalid_state: "This link has expired or was already used. Start connecting again.",
  connection_failed: "Your accounting system didn't approve the connection.",
  forbidden: "Only your company's administrator can connect, after signing in recently.",
};

/** SPEC-020 AC-2 (TASK-036 D1): the provider sends the browser here; the flow is completed with
 * this person's own sign-in, then they return to their engagement. */
export function ConnectCallback(): JSX.Element {
  const navigate = useNavigate();
  const { searchStr } = useLocation();
  const [failure, setFailure] = useState<string | null>(null);
  const sent = useRef(false);
  useEffect(() => {
    if (accessToken() === null) {
      void signIn(`/client/connect/callback${searchStr}`);
      return;
    }
    if (sent.current) return;
    sent.current = true;
    const params = new URLSearchParams(searchStr);
    const state = params.get("state") ?? "";
    const code = params.get("code") ?? "";
    // The code and state leave the address bar before anything else happens.
    void navigate({ to: ".", search: {}, replace: true });
    if (state === "" || code === "") {
      setFailure(REASONS.connection_failed ?? "");
      return;
    }
    void complete({ body: { state, code }, throwOnError: true })
      .then(({ data }) =>
        navigate({
          to: "/client/engagements/$engagementId",
          params: { engagementId: data.engagement_id },
        }),
      )
      .catch((error: unknown) => {
        const code = errorMessage(error);
        setFailure(REASONS[code] ?? code);
      });
  }, [navigate, searchStr]);
  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col justify-center gap-4 bg-ground p-6">
      {failure === null ? (
        <Spinner label="Finishing the connection…" />
      ) : (
        <Alert title="Not connected">
          {failure}{" "}
          <Link to="/client" className="text-accent hover:underline">
            Back to your engagements
          </Link>
        </Alert>
      )}
    </main>
  );
}

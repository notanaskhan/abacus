import { complete } from "@abacus/api-client";
import { Alert, Spinner } from "@abacus/ui";
import { Link, useLocation, useNavigate } from "@tanstack/react-router";
import { type JSX, useEffect, useRef, useState } from "react";
import { errorMessage } from "../api";
import { useSignedIn } from "../app-core/auth";

const REASONS: Record<string, string> = {
  invalid_state: "This link has expired or was already used. Start connecting again.",
  connection_failed: "Your accounting system didn't approve the connection.",
  forbidden: "Only your company's administrator can connect, after signing in recently.",
};

/** A-02-T26 (DEC-709): the provider's company id, when it sends one, rides inside the code. */
export function withRealm(code: string, realm: string | null): string {
  return code !== "" && realm !== null && realm !== "" ? `${code}~${realm}` : code;
}

/** SPEC-020 AC-2 (TASK-036 D1): the provider sends the browser here; the flow is completed with
 * this person's own sign-in, then they return to their engagement. */
export function ConnectCallback(): JSX.Element {
  const navigate = useNavigate();
  const { searchStr } = useLocation();
  const [failure, setFailure] = useState<string | null>(null);
  const sent = useRef(false);
  const signedIn = useSignedIn(`/client/connect/callback${searchStr}`);
  useEffect(() => {
    if (!signedIn || sent.current) return;
    sent.current = true;
    const params = new URLSearchParams(searchStr);
    const state = params.get("state") ?? "";
    // A-02-T26 (DEC-709): QuickBooks Online names the client's company only here (`realmId`);
    // it travels inside the code as `<code>~<realmId>` so the completion contract is unchanged.
    const code = withRealm(params.get("code") ?? "", params.get("realmId"));
    // The code and state leave the address bar before anything else happens.
    void navigate({ to: ".", search: {}, replace: true });
    if (state === "" || code === "") {
      setFailure(REASONS.connection_failed ?? "");
      return;
    }
    void complete({ body: { state, code }, throwOnError: true })
      .then(({ data }) => {
        // A-02-T28: an entity flow (POR-16) returns to the portal's Connections, which reads
        // the cards again; the legacy engagement flow returns to its engagement.
        if (data.client_entity_id != null) {
          window.location.assign(`/connections?entity=${encodeURIComponent(data.client_entity_id)}`);
          return undefined;
        }
        return navigate({
          to: "/client/engagements/$engagementId",
          params: { engagementId: data.engagement_id },
        });
      })
      .catch((error: unknown) => {
        const code = errorMessage(error);
        setFailure(REASONS[code] ?? code);
      });
  }, [navigate, searchStr, signedIn]);
  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col justify-center gap-4 bg-shell p-6">
      {failure === null ? (
        <Spinner label="Finishing the connection…" />
      ) : (
        <Alert title="Not connected">
          {failure}{" "}
          <Link to="/client" className="text-espresso hover:underline">
            Back to your engagements
          </Link>
        </Alert>
      )}
    </main>
  );
}

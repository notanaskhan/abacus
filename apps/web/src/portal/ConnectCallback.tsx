import { complete, handoff } from "@abacus/api-client";
import { Alert, Spinner } from "@abacus/ui";
import { type JSX, useEffect, useRef, useState } from "react";
import { ensurePortalSession, goToSignIn } from "../app-core/auth/bff";

export const CALLBACK_PATH = "/client/connect/callback";
// A host name only (no scheme, port, path, user or query): what the API stores and answers.
const HOST_NAME = /^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*$/;

const EXPIRED = "This link has expired or was already used. Start connecting again.";
const REASONS: Record<string, string> = {
  invalid_state: EXPIRED,
  connection_failed: "Your accounting system didn't approve the connection.",
  forbidden: "Only your company's administrator can connect, after signing in recently.",
};

/** The API's error code (`{detail}`), or a generic one: never a message from elsewhere. */
function detailOf(error: unknown): string {
  if (typeof error === "object" && error !== null && "detail" in error) {
    const detail = error.detail;
    if (typeof detail === "string") return detail;
  }
  return "connection_failed";
}

/** A-02-T26 (DEC-709): the provider's company id, when it sends one, rides inside the code. */
export function withRealm(code: string, realm: string | null): string {
  return code !== "" && realm !== null && realm !== "" ? `${code}~${realm}` : code;
}

/** Where the connect host sends the browser on: the stored host, the fixed path, and the
 * provider's query exactly as it arrived. Null for anything that is not a host name. */
export function handBackUrl(originHost: string, search: string): string | null {
  if (!HOST_NAME.test(originHost) || originHost.length > 253) return null;
  return `https://${originHost}${CALLBACK_PATH}${search}`;
}

type Pending = { state: string; code: string };
// Held in this tab across a sign-in on this host only, then removed on first read.
const PENDING_KEY = "connect.pending";

function keepPending(pending: Pending): void {
  try {
    sessionStorage.setItem(PENDING_KEY, JSON.stringify(pending));
  } catch {
    // no storage: the person starts connecting again after signing in
  }
}

function takePending(): Pending | null {
  try {
    const raw = sessionStorage.getItem(PENDING_KEY);
    sessionStorage.removeItem(PENDING_KEY);
    const found: unknown = raw === null ? null : JSON.parse(raw);
    if (
      typeof found === "object" &&
      found !== null &&
      "state" in found &&
      "code" in found &&
      typeof found.state === "string" &&
      typeof found.code === "string" &&
      found.state !== "" &&
      found.code !== ""
    ) {
      return { state: found.state, code: found.code };
    }
  } catch {
    // unreadable: as if nothing were held
  }
  return null;
}

type Props = {
  /** Leaves for another host (tests replace it). */
  leave?: (url: string) => void;
  /** The portal session on this host (tests replace it). */
  ensureSession?: () => Promise<boolean>;
};

/** A-02-T33 (DEC-3902): the provider returns every firm's flow to one registered host,
 * `connect.<domain>`, where no portal session is valid (ADR-163 §5). This page asks the API which
 * host the flow began on and sends the browser there with the query unchanged; on that host it
 * completes with the person's own portal session and returns to Connections. The API names the
 * host only, and only for a live state; this page never takes a host from the query. */
export function PortalConnectCallback({
  leave = (url) => {
    window.location.replace(url);
  },
  ensureSession = () => ensurePortalSession(),
}: Props): JSX.Element {
  const [failure, setFailure] = useState<string | null>(null);
  const sent = useRef(false);
  useEffect(() => {
    if (sent.current) return;
    sent.current = true;
    const search = window.location.search;
    const params = new URLSearchParams(search);
    const state = params.get("state") ?? "";
    const code = withRealm(params.get("code") ?? "", params.get("realmId"));
    void (async () => {
      let pending: Pending | null;
      if (state === "" && code === "") {
        pending = takePending(); // back from signing in on this host
      } else if (state === "" || code === "") {
        pending = null;
      } else {
        let origin: string;
        try {
          const { data } = await handoff({ body: { state }, throwOnError: true });
          origin = data.origin_host;
        } catch {
          setFailure(EXPIRED); // one answer: unknown, used, expired or not a host of the firm
          return;
        }
        if (origin !== window.location.hostname) {
          const url = handBackUrl(origin, search);
          if (url === null) setFailure(EXPIRED);
          else leave(url);
          return;
        }
        pending = { state, code };
      }
      // The code and state leave the address bar (and never ride in a sign-in URL).
      window.history.replaceState(null, "", CALLBACK_PATH);
      if (pending === null) {
        setFailure(REASONS.connection_failed ?? "");
        return;
      }
      if (!(await ensureSession())) {
        keepPending(pending);
        goToSignIn(CALLBACK_PATH);
        return;
      }
      try {
        const { data } = await complete({ body: pending, throwOnError: true });
        const entity = data.client_entity_id;
        window.location.assign(
          entity == null ? "/connections" : `/connections?entity=${encodeURIComponent(entity)}`,
        );
      } catch (error: unknown) {
        setFailure(REASONS[detailOf(error)] ?? REASONS.connection_failed ?? "");
      }
    })();
  }, [ensureSession, leave]);
  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col justify-center gap-4 bg-shell p-6">
      {failure === null ? (
        <Spinner label="Finishing the connection…" />
      ) : (
        <Alert title="Not connected">{failure}</Alert>
      )}
    </main>
  );
}

import { getThreadOptions } from "@abacus/api-client/query";
import { FlagOffState } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { createRoute } from "@tanstack/react-router";
import type { JSX } from "react";
import { FeatureGate } from "../../app-core/flags";
import { useSession } from "../../app-core/session";
import { appRoute, lazyScreen } from "../root";

// INB-01 and INB-02 live (N-01-T23; docs/screens/INB-01.md, INB-02.md): `/inbox` behind
// `inbox.firm_intake`. `?thread=<uuid>` selects a thread; `?ov=file&message=<uuid>` opens INB-02's
// triage sheet over it; `?ov=log-intake` opens Log received documents (DV-1). The rail polls every
// 10 s and the triage sheet every 2 s while visible (DEC-23).

const Inbox = lazyScreen(async () => (await import("../../screens/INB-01")).INB01);
const Triage = lazyScreen(async () => (await import("../../screens/INB-02")).INB02);
const LogIntake = lazyScreen(
  async () => (await import("../../domain/inbox/LogIntakeSheet")).LogIntakeSheet,
);

interface InboxSearch {
  thread?: string;
  ov?: "file" | "log-intake";
  message?: string;
}

function validateInboxSearch(search: Record<string, unknown>): InboxSearch {
  const text = (key: string): string | undefined => {
    const value = search[key];
    return typeof value === "string" && value !== "" ? value : undefined;
  };
  const ov = text("ov");
  const thread = text("thread");
  const message = text("message");
  return {
    ...(thread === undefined ? {} : { thread }),
    ...(ov === "file" || ov === "log-intake" ? { ov } : {}),
    ...(message === undefined ? {} : { message }),
  };
}

function TriageOver({
  thread,
  message,
  onClose,
}: {
  thread: string | undefined;
  message: string;
  onClose: () => void;
}): JSX.Element {
  // The thread INB-01 already read (the same query key): the sheet's "{subject} · {sender}".
  const detail = useQuery({
    ...getThreadOptions({ path: { thread_id: thread ?? "" } }),
    enabled: thread !== undefined,
  });
  return (
    <Triage
      messageId={message}
      subject={detail.data?.thread.subject_display ?? ""}
      sender={detail.data?.thread.sender_display ?? ""}
      onClose={onClose}
    />
  );
}

export const inboxRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/inbox",
  validateSearch: validateInboxSearch,
  component: function InboxPage(): JSX.Element {
    const search = inboxRoute.useSearch();
    const navigate = inboxRoute.useNavigate();
    const viewer = useSession().user?.displayName ?? "";
    const base = search.thread === undefined ? {} : { thread: search.thread };
    const close = (): void => {
      void navigate({ search: base, replace: true });
    };
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <FeatureGate
          flag="inbox.firm_intake"
          fallback={<FlagOffState flag="inbox.firm_intake" label="Inbox" />}
        >
          <Inbox
            initialThread={search.thread ?? null}
            onSelect={(thread) => {
              void navigate({ search: { thread }, replace: true });
            }}
            onFile={(message) => {
              void navigate({ search: { ...base, ov: "file", message } });
            }}
            onLogIntake={() => {
              void navigate({ search: { ...base, ov: "log-intake" } });
            }}
          />
          {search.ov === "file" && search.message !== undefined && (
            <TriageOver thread={search.thread} message={search.message} onClose={close} />
          )}
          {search.ov === "log-intake" && <LogIntake open viewer={viewer} onClose={close} />}
        </FeatureGate>
      </div>
    );
  },
});

export const inboxRoutes = [inboxRoute] as const;

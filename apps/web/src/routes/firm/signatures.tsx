import { FlagOffState } from "@abacus/ui";
import { createRoute } from "@tanstack/react-router";
import type { JSX } from "react";
import { FeatureGate } from "../../app-core/flags";
import { appRoute, lazyScreen } from "../root";

// SIG-01 live (N-02-T40; docs/screens/SIG-01.md): `/signatures` behind `signatures.envelopes`.
// `?tab=to_send|out|completed|expired` picks the tab, `?envelope=<uuid>` opens the O2 evidence
// drawer and `?ov=import` opens Import signed package (r, DF-12).

const Hub = lazyScreen(async () => (await import("../../screens/SIG-01")).SIG01);

const TABS = ["to_send", "out", "completed", "expired"] as const;
type Sig01Tab = (typeof TABS)[number];

interface SignaturesSearch {
  tab?: Sig01Tab;
  envelope?: string;
  ov?: "import";
}

function validateSignaturesSearch(search: Record<string, unknown>): SignaturesSearch {
  const tab = TABS.find((t) => t === search.tab);
  const envelope = typeof search.envelope === "string" ? search.envelope : "";
  return {
    ...(tab === undefined ? {} : { tab }),
    ...(envelope === "" ? {} : { envelope }),
    ...(search.ov === "import" ? { ov: "import" as const } : {}),
  };
}

export const signaturesRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/signatures",
  validateSearch: validateSignaturesSearch,
  component: function SignaturesPage(): JSX.Element {
    const search = signaturesRoute.useSearch();
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <FeatureGate
          flag="signatures.envelopes"
          fallback={<FlagOffState flag="signatures.envelopes" label="Signatures" />}
        >
          <Hub
            {...(search.tab === undefined ? {} : { initialTab: search.tab })}
            initialEnvelope={search.envelope ?? null}
            initialImport={search.ov === "import"}
          />
        </FeatureGate>
      </div>
    );
  },
});

export const signatureRoutes = [signaturesRoute] as const;

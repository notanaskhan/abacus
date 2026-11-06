import { riskRegisterOptions } from "@abacus/api-client/query";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "@tanstack/react-router";
import type { JSX } from "react";
import { useOverlays } from "../../app-core/overlay-host";
import type { OverlayRenderProps } from "../../app-core/overlays";
import { useAuditCockpit } from "../../domain/audits";
import { RiskDrawer } from "./RiskDrawer";

// AUD-08's public entry (A-04-T20): the register page, and the `?ov=risk:<code>` drawer host the
// overlay registry renders (the audit from the route, the risk by its code on the register).

export { RiskRegisterPage } from "./Register";
export { RiskDrawer } from "./RiskDrawer";

export function RiskDrawerHost({ ref, close }: OverlayRenderProps): JSX.Element | null {
  const params: { auditId?: string } = useParams({ strict: false });
  const auditId = params.auditId ?? "";
  const overlays = useOverlays();
  const cockpit = useAuditCockpit(auditId);
  const engagementId = cockpit.data?.engagement_id;
  const register = useQuery({
    ...riskRegisterOptions({ path: { engagement_id: engagementId ?? "" } }),
    enabled: engagementId !== undefined,
  });
  const risk = register.data?.risks.find((r) => r.code === ref.args[0]);
  if (engagementId === undefined || risk === undefined || register.data === undefined) return null;
  return (
    <RiskDrawer
      engagementId={engagementId}
      risk={risk}
      onClose={close}
      onDecide={(cardId) => {
        overlays.open("decision", cardId);
      }}
    />
  );
}

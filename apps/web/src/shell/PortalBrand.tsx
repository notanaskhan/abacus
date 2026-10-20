import { meOptions } from "@abacus/api-client/query";
import { useQuery } from "@tanstack/react-query";
import type { JSX } from "react";

/** The portal is the firm's (TASK-099, the plan's white-label rule): the client sees their
 * firm's name, never the product's. Before a firm is known, a neutral "Client portal". */
export function PortalBrand(): JSX.Element {
  const me = useQuery({ ...meOptions(), retry: false });
  const tenant = me.data?.active_tenant_id ?? null;
  const firm =
    me.data?.memberships.find((m) => m.kind === "client" && m.tenant_id === tenant)?.firm_name ??
    me.data?.memberships.find((m) => m.kind === "client")?.firm_name ??
    null;
  const name = firm ?? "Client portal";
  return (
    <span className="flex items-center gap-2 text-[15px] font-medium tracking-[-0.02em]">
      <span
        aria-hidden="true"
        className="flex size-[22px] items-center justify-center rounded-[6px] bg-espresso text-[11.5px] text-on-dark"
      >
        {name.charAt(0).toUpperCase()}
      </span>
      {name}
    </span>
  );
}

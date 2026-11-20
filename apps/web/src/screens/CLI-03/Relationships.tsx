// CLI-03 on the live client (T-06-T40): the graph (`GET /v1/clients/{id}/relationship-graph`), the
// TIN reveal (logged by the server before it answers the value), Add relationship (O3), end, and
// the viewer's saved layout (`PUT /v1/users/me/graph-layouts/{id}`).
import {
  graphLayoutMutation,
  relationshipCreateMutation,
  relationshipEndMutation,
  relationshipGraphOptions,
  relationshipGraphQueryKey,
} from "@abacus/api-client/query";
import type { GraphView } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { CLI03 } from "./index";

export function Relationships({ clientId }: { clientId: string }): JSX.Element {
  const path = { client_id: clientId };
  const client = useQueryClient();
  const graph = useQuery(relationshipGraphOptions({ path }));
  const [view, setView] = useState<GraphView>("graph");
  const [selected, setSelected] = useState<string | null>(null);
  const refresh = (): void => {
    void client.invalidateQueries({ queryKey: relationshipGraphQueryKey({ path }) });
  };
  const create = useMutation({ ...relationshipCreateMutation(), onSuccess: refresh });
  const end = useMutation({ ...relationshipEndMutation(), onSuccess: refresh });
  const layout = useMutation(graphLayoutMutation());
  return (
    <CLI03
      graph={graph.data}
      view={view}
      onView={setView}
      selected={selected ?? graph.data?.selected_node_id ?? null}
      onSelect={setSelected}
      onLayout={(positions) => {
        layout.mutate({
          path,
          body: {
            positions: Object.fromEntries(
              Object.entries(positions).map(([id, p]) => [id, [p.x, p.y] as [number, number]]),
            ),
          },
        });
      }}
      onAdd={(b) => {
        create.mutate({
          path,
          body: {
            from_node_id: b.from,
            to_node_id: b.to,
            kind: b.kind,
            percent: b.percent,
            effective_from: b.effectiveFrom,
          },
        });
      }}
      onEnd={(edgeId, reason) => {
        end.mutate({
          path: { rel_id: edgeId },
          body: { reason, effective_to: new Date().toISOString().slice(0, 10) },
        });
      }}
    />
  );
}

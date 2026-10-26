import { Suspense, lazy } from "react";
import { registerOverlay } from "../../app-core/overlays";

// WB-09 (P-09-T10, T13): the run trace drawer on any firm route, `?ov=run-trace:<runId>`.
// Opening pushes history, so Back closes it. The whole agents domain is its own chunk, loaded on
// open, so the key is written here rather than imported (domain/agents/links.ts holds the same
// key; overlay.test.tsx keeps them equal).

export const RUN_TRACE_KEY = "run-trace";

const TraceDrawer = lazy(async () => ({
  default: (await import("../../domain/agents")).TraceDrawer,
}));

registerOverlay(RUN_TRACE_KEY, {
  layer: "drawer",
  render: ({ ref, close }) => {
    const runId = ref.args[0];
    return runId === undefined ? null : (
      <Suspense fallback={null}>
        <TraceDrawer runId={runId} onClose={close} />
      </Suspense>
    );
  },
});

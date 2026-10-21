import { useRouterState } from "@tanstack/react-router";

/** A path parameter of the current route. The area files can't see the registered route types
 * (the router that registers them imports these files), so parameters are read untyped here. */
export function useParam(name: string): string {
  return useRouterState({
    select: (state) => {
      const params: unknown = state.matches.at(-1)?.params;
      if (typeof params !== "object" || params === null) return "";
      const value = (params as Record<string, unknown>)[name];
      return typeof value === "string" ? value : "";
    },
  });
}

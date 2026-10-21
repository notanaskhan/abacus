import { createRoute, createRouter, lazyRouteComponent } from "@tanstack/react-router";
import { firmRoutes } from "./routes/firm";
import { portalRoutes } from "./routes/portal";
import { appRoute, callbackRoute, rootRoute } from "./routes/root";

// The route tree (ADR-011), assembled from its areas (F-03-T17): routes/root (shell, sign-in
// callback), routes/firm/* (the firm's areas in bar order), routes/portal (the client portal).

// F-05-T09 (SPEC-048): the /components gallery. `VITE_UI_GALLERY=1` compiles it (dev, fixture and
// opt-in preview builds); a production build constant-folds the flag away, so neither the routes
// nor the lazy chunk behind them reach `dist/`. It sits outside the app shell and calls no API.
const GALLERY = import.meta.env.VITE_UI_GALLERY === "1";
function galleryRoutes() {
  const pages = (
    name: "GalleryLayout" | "GalleryIndex" | "TokensPage" | "IconsPage" | "ScreenPage",
  ) => lazyRouteComponent(() => import("./gallery/pages"), name);
  const layout = createRoute({
    getParentRoute: () => rootRoute,
    path: "/components",
    // The query parameters are read where they are used (gallery/fixture-mode.ts).
    component: pages("GalleryLayout"),
  });
  return [
    layout.addChildren([
      createRoute({ getParentRoute: () => layout, path: "/", component: pages("GalleryIndex") }),
      createRoute({
        getParentRoute: () => layout,
        path: "tokens",
        component: pages("TokensPage"),
      }),
      createRoute({
        getParentRoute: () => layout,
        path: "icons",
        component: pages("IconsPage"),
      }),
      createRoute({
        getParentRoute: () => layout,
        path: "screens/$id",
        component: pages("ScreenPage"),
      }),
    ]),
  ];
}

const routeTree = rootRoute.addChildren([
  callbackRoute,
  ...portalRoutes,
  // Typed as no routes: the gallery stays out of the app's route types (links to it are plain).
  ...(GALLERY ? (galleryRoutes() as unknown as []) : []),
  appRoute.addChildren([...firmRoutes]),
]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

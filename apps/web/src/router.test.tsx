import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

afterEach(cleanup);

describe("ac18 router", () => {
  it("shows a not-found page with a link to the engagements", async () => {
    // The router reads the URL when it is created, so set it before importing.
    window.history.pushState({}, "", "/no/such/page");
    const { router } = await import("./router");
    render(
      <QueryClientProvider client={new QueryClient()}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );
    expect(await screen.findByText("Page not found")).toBeTruthy();
    expect(screen.getByRole("link", { name: /engagements/i }).getAttribute("href")).toBe("/");
  });
});

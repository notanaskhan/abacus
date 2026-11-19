// G-04-T17 (TASK-8703; DEC-5701): the five undesigned console sections render from their fixture
// scenarios, and the drafter's own draft shows Publish disabled with the reason beside it.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  STATUS_COMPONENTS,
  consoleConversation,
  consoleIncidents,
  consolePlanRequests,
  consolePublications,
  consoleQueue,
  consoleSessions,
} from "../../fixtures/seed/console-sections";
import { SECTIONS_COPY as C } from "./copy";
import { PlanRequestsCard, PlanRequestsTile } from "./PlanRequestsCard";
import { Publications } from "./Publications";
import { Status } from "./Status";
import { SupportQueue } from "./SupportQueue";
import { SupportSessions } from "./SupportSessions";

afterEach(cleanup);

describe("G-04-T17 console sections", () => {
  it("lists support sessions with scope, status and the firm approver", () => {
    render(<SupportSessions data={consoleSessions()} />);
    const rows = screen.getAllByRole("row").slice(1);
    expect(rows).toHaveLength(2);
    expect(within(rows[1] as HTMLElement).getByText("Felix Andersen")).toBeTruthy();
    expect(screen.getAllByText(C.sessions.scope.integration_settings ?? "")).toHaveLength(2);
    expect(screen.getByText("Requested", { selector: "[data-session] *" })).toBeTruthy();
  });

  it("shows the drafter's own draft with Publish disabled and the reason", () => {
    const onPublish = vi.fn();
    render(<Publications data={consolePublications()} onPublish={onPublish} />);
    const [own, other] = screen.getAllByRole("button", { name: C.publications.publish });
    expect(own).toHaveProperty("disabled", true);
    expect(own?.getAttribute("aria-describedby")).toBeTruthy();
    expect(screen.getByText(C.publications.ownDraft)).toBeTruthy();
    expect(other).toHaveProperty("disabled", false);
    fireEvent.click(other as HTMLElement);
    expect(onPublish).toHaveBeenCalledOnce();
  });

  it("posts an incident only with a title and a public note, and resolves with a note", () => {
    const onPost = vi.fn();
    const onResolve = vi.fn();
    render(
      <Status
        data={consoleIncidents()}
        components={STATUS_COMPONENTS}
        onPost={onPost}
        onResolve={onResolve}
      />,
    );
    expect(screen.getByText("CCH Axcess exports delayed")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: C.status.post }));
    const post = screen.getByRole("button", { name: C.status.sheet.post });
    expect(post).toHaveProperty("disabled", true);
    fireEvent.change(screen.getByLabelText(C.status.sheet.title), {
      target: { value: "Portal sign-in slow" },
    });
    fireEvent.change(screen.getByLabelText(C.status.sheet.note), {
      target: { value: "Sign-in takes longer than usual." },
    });
    fireEvent.click(screen.getByRole("button", { name: C.status.sheet.post }));
    expect(onPost).toHaveBeenCalledWith(
      expect.objectContaining({ title: "Portal sign-in slow", severity: "degraded" }),
    );
    fireEvent.click(screen.getByText("CCH Axcess exports delayed"));
    fireEvent.change(screen.getByLabelText(C.status.sheet.updateNote), {
      target: { value: "Exports are back to normal." },
    });
    fireEvent.click(screen.getByRole("button", { name: C.status.sheet.resolve }));
    expect(onResolve).toHaveBeenCalledOnce();
  });

  it("lists the queue unanswered first and opens a conversation on the chat thread", () => {
    const { rerender } = render(
      <SupportQueue data={consoleQueue()} open onOpenChange={() => undefined} />,
    );
    expect(screen.getByText(C.queue.unanswered)).toBeTruthy();
    rerender(
      <SupportQueue
        data={consoleQueue()}
        detail={consoleConversation()}
        open
        onOpenChange={() => undefined}
      />,
    );
    expect(screen.getByText("Can you check Kevin's export from Friday too?")).toBeTruthy();
  });

  it("counts plan requests on the tile and marks one applied from the tenant card", () => {
    const onMark = vi.fn();
    render(
      <>
        <PlanRequestsTile data={consolePlanRequests()} />
        <PlanRequestsCard
          tenantCode="tnt_bh01"
          data={consolePlanRequests()}
          onMarkApplied={onMark}
        />
      </>,
    );
    expect(screen.getByText(C.planRequests.approvedBy("Margaret Okonkwo"))).toBeTruthy();
    expect(screen.getByText(/46 → 48/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: C.planRequests.markApplied }));
    expect(onMark).toHaveBeenCalledOnce();
  });
});

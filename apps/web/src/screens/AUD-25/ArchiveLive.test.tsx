// A-07-T47 (TASK-6737): AUD-25 on the server's data: the clock, the nine items, the binder and the
// lock behind "Assembly is complete"; no lock control without `archive.lock`, none after lock.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AuditArchiveStateOut } from "@abacus/api-client";
import { aud25 } from "../../fixtures/seed/audit-completion";
import { ArchiveLive, clockWords } from "./ArchiveLive";

afterEach(cleanup);

const ready = (): AuditArchiveStateOut => ({
  ...aud25("b"),
  checklist_done: 9,
  checklist_total: 9,
  allowed_actions: ["archive.lock"],
});
const lock = (): HTMLButtonElement | null =>
  screen.queryByRole("button", { name: /Lock archive…|Locking…/ });

describe("AUD-25 live", () => {
  it("the clock reads in days, red at 7 or fewer", () => {
    expect(clockWords(47)).toBe("Archive in 47 days");
    expect(clockWords(1)).toBe("Archive in 1 day");
    expect(clockWords(null)).toBeNull();
    render(<ArchiveLive archive={aud25("a")} />);
    expect(screen.getByText("Archive in 47 days")).toBeTruthy();
    expect(document.querySelector("[data-clock='ok']")).not.toBeNull();
    cleanup();
    render(<ArchiveLive archive={{ ...aud25("a"), days_left: 5 }} />);
    expect(document.querySelector("[data-clock='risk']")).not.toBeNull();
  });

  it("a: 8 of 9 keeps the lock disabled; without archive.lock there is no control", () => {
    render(
      <ArchiveLive
        archive={{ ...aud25("a"), allowed_actions: ["archive.lock"] }}
        onLock={vi.fn()}
      />,
    );
    expect(lock()?.disabled).toBe(true);
    cleanup();
    render(<ArchiveLive archive={aud25("a")} onLock={vi.fn()} />);
    expect(lock()).toBeNull();
  });

  it("b: 9 of 9 locks only after Assembly is complete", () => {
    const onLock = vi.fn();
    render(<ArchiveLive archive={ready()} onLock={onLock} />);
    fireEvent.click(lock() as HTMLButtonElement);
    expect(screen.getByRole<HTMLButtonElement>("button", { name: "Lock archive" }).disabled).toBe(
      true,
    );
    fireEvent.click(screen.getByRole("checkbox", { name: "Assembly is complete" }));
    fireEvent.click(screen.getByRole("button", { name: "Lock archive" }));
    expect(onLock).toHaveBeenCalledTimes(1);
  });

  it("while ArchiveLockWorkflow seals the control reads Locking…", () => {
    render(<ArchiveLive archive={ready()} running onLock={vi.fn()} />);
    expect(lock()?.textContent).toBe("Locking…");
    expect(lock()?.disabled).toBe(true);
  });

  it("c: locked by Hannah Leclerc with the short seal and no lock or delete control", () => {
    render(<ArchiveLive archive={aud25("c")} onLock={vi.fn()} tz="America/Chicago" />);
    const line = document.querySelector("[data-locked='true']")?.textContent ?? "";
    expect(line).toContain("Hannah Leclerc");
    expect(line).toContain("seal 7c41…a9e2");
    expect(lock()).toBeNull();
    expect(screen.queryByRole("button", { name: /Delete/ })).toBeNull();
  });
});

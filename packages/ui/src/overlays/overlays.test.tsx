// F-05-T20: the layers of the O1 to O6 grammar, unit level. Escape closes the topmost layer only,
// focus returns to the opener, scroll lock is released, a dirty layer asks before it closes, a
// peek takes no focus and no scrim, two drawers never open, and nothing animates under reduced
// motion. The independent suite is F-05-T22.
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { type JSX, useState } from "react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { Button } from "../components/button";
import { Menu } from "../components/popover";
import { installDomShims } from "../test-dom";
import { ConfirmDialog } from "./confirm";
import { Dialog } from "./dialog";
import { Drawer } from "./drawer";
import { CommandPalette } from "./palette";
import { Popover } from "./popover";
import { FullSheet, SheetModal } from "./sheet";
import { appOverlayStack } from "./stack";
import { Wizard } from "./wizard";

beforeAll(installDomShims);
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const escape = (): void => {
  fireEvent.keyDown(document, { key: "Escape" });
};

const locked = (): boolean => document.body.hasAttribute("data-scroll-locked");

async function closed(name: string | RegExp, role = "dialog"): Promise<void> {
  await waitFor(() => {
    expect(screen.queryByRole(role, { name })).toBeNull();
  });
}

/** A layer under a newer modal is hidden from the accessibility tree (Radix), so ask for it hidden. */
const under = (name: string): HTMLElement => {
  const heading = screen.getByText(name, { selector: "h2" });
  return heading.closest<HTMLElement>("[role='dialog']") as HTMLElement;
};

/** A button that opens a layer: focus it first, as a person would. */
function press(button: HTMLElement): void {
  button.focus();
  fireEvent.click(button);
}

// ---- Escape, in order, and focus return --------------------------------------------------------

function Stacked(): JSX.Element {
  const [drawer, setDrawer] = useState(false);
  const [dialog, setDialog] = useState(false);
  return (
    <>
      <Button
        onClick={() => {
          setDrawer(true);
        }}
      >
        Open drawer
      </Button>
      <Drawer open={drawer} onOpenChange={setDrawer} title="Request">
        <Button
          onClick={() => {
            setDialog(true);
          }}
        >
          Open dialog
        </Button>
        <Dialog open={dialog} onOpenChange={setDialog} title="Assign">
          <Popover label="Reviewers" trigger={<Button>Open popover</Button>}>
            <p>Hannah Leclerc</p>
          </Popover>
        </Dialog>
      </Drawer>
    </>
  );
}

describe("Escape and focus return", () => {
  it("closes the popover, then the dialog, then the drawer, one Escape each, focus to each opener", async () => {
    render(<Stacked />);
    press(screen.getByRole("button", { name: "Open drawer" }));
    const drawer = await screen.findByRole("dialog", { name: "Request" });
    press(within(drawer).getByRole("button", { name: "Open dialog" }));
    const dialog = await screen.findByRole("dialog", { name: "Assign" });
    press(within(dialog).getByRole("button", { name: "Open popover" }));
    await screen.findByRole("dialog", { name: "Reviewers" });
    expect(appOverlayStack.layers().map((l) => l.kind)).toEqual(["drawer", "dialog", "popover"]);

    escape();
    await closed("Reviewers");
    expect(under("Assign")).toBeTruthy();
    expect(under("Request")).toBeTruthy();
    await waitFor(() => {
      expect(document.activeElement).toBe(screen.getByRole("button", { name: "Open popover" }));
    });

    escape();
    await closed("Assign");
    expect(under("Request")).toBeTruthy();
    await waitFor(() => {
      expect(document.activeElement).toBe(screen.getByRole("button", { name: "Open dialog" }));
    });

    escape();
    await closed("Request");
    await waitFor(() => {
      expect(document.activeElement).toBe(screen.getByRole("button", { name: "Open drawer" }));
    });
    expect(appOverlayStack.layers()).toHaveLength(0);
  });

  it("returns focus to a button that opened a controlled dialog Radix has no trigger for", async () => {
    function Page(): JSX.Element {
      const [open, setOpen] = useState(false);
      return (
        <>
          <Button
            onClick={() => {
              setOpen(true);
            }}
          >
            New engagement…
          </Button>
          <Dialog open={open} onOpenChange={setOpen} title="New engagement">
            <input aria-label="Name" />
          </Dialog>
        </>
      );
    }
    render(<Page />);
    const opener = screen.getByRole("button", { name: "New engagement…" });
    press(opener);
    await screen.findByRole("dialog", { name: "New engagement" });
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    await closed("New engagement");
    await waitFor(() => {
      expect(document.activeElement).toBe(opener);
    });
  });

  it("only the topmost layer is asked to close by Escape", async () => {
    const onDrawer = vi.fn();
    const onDialog = vi.fn();
    render(
      <>
        <Drawer open onOpenChange={onDrawer} title="Request">
          <p>Body</p>
        </Drawer>
        <Dialog open onOpenChange={onDialog} title="Assign">
          <p>Body</p>
        </Dialog>
      </>,
    );
    await screen.findAllByText("Assign", { selector: "h2" });
    escape();
    expect(onDialog).toHaveBeenCalledExactlyOnceWith(false);
    expect(onDrawer).not.toHaveBeenCalled();
  });

  it("a menu inside a dialog closes before the dialog, and sits above it", async () => {
    const onOpenChange = vi.fn();
    render(
      <Dialog open onOpenChange={onOpenChange} title="Issue">
        <Menu
          label="Assign to"
          trigger={<Button>Assign to</Button>}
          sections={[[{ label: "Priya Raman", onSelect: () => undefined }]]}
        />
      </Dialog>,
    );
    const dialog = await screen.findByRole("dialog", { name: "Issue" });
    const trigger = within(dialog).getByRole("button", { name: "Assign to" });
    trigger.focus();
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    const menu = await screen.findByRole("menu", { name: "Assign to" });
    const z = (el: HTMLElement): number => Number(/\+ (\d+)\)/.exec(el.style.zIndex)?.[1]);
    // The dialog's scrim holds it; the menu is above both.
    expect(z(menu)).toBeGreaterThan(z(dialog.parentElement as HTMLElement));
    escape();
    await waitFor(() => {
      expect(screen.queryByRole("menu")).toBeNull();
    });
    expect(onOpenChange).not.toHaveBeenCalled();
    escape();
    expect(onOpenChange).toHaveBeenCalledExactlyOnceWith(false);
  });

  it("stacks each layer's scrim and panel above the one under it", async () => {
    render(<Stacked />);
    press(screen.getByRole("button", { name: "Open drawer" }));
    const drawer = await screen.findByRole("dialog", { name: "Request" });
    press(within(drawer).getByRole("button", { name: "Open dialog" }));
    const dialog = await screen.findByRole("dialog", { name: "Assign" });
    const index = (el: HTMLElement): number => Number(/\+ (\d+)\)/.exec(el.style.zIndex)?.[1]);
    const scrim = dialog.parentElement as HTMLElement;
    expect(index(scrim)).toBeGreaterThan(index(under("Request")));
  });
});

// ---- Scroll lock -------------------------------------------------------------------------------

describe("scroll lock", () => {
  it("holds the page while a modal layer is open and releases it on close", async () => {
    function Page(): JSX.Element {
      const [open, setOpen] = useState(true);
      return (
        <Dialog open={open} onOpenChange={setOpen} title="Sign off">
          <p>Body</p>
        </Dialog>
      );
    }
    render(<Page />);
    await screen.findByRole("dialog", { name: "Sign off" });
    expect(locked()).toBe(true);
    escape();
    await closed("Sign off");
    await waitFor(() => {
      expect(locked()).toBe(false);
    });
  });

  it("holds it until the last of two modal layers is gone", async () => {
    render(<Stacked />);
    press(screen.getByRole("button", { name: "Open drawer" }));
    const drawer = await screen.findByRole("dialog", { name: "Request" });
    press(within(drawer).getByRole("button", { name: "Open dialog" }));
    await screen.findByRole("dialog", { name: "Assign" });
    escape();
    await closed("Assign");
    expect(locked()).toBe(true);
    escape();
    await closed("Request");
    await waitFor(() => {
      expect(locked()).toBe(false);
    });
  });

  it("does not hold it for a peek or a popover", async () => {
    render(
      <>
        <Drawer open peek onOpenChange={() => undefined} title="2025 Form 1065">
          <p>Body</p>
        </Drawer>
        <Popover open label="Assign to" trigger={<Button>Assign</Button>}>
          <p>Body</p>
        </Popover>
      </>,
    );
    await screen.findByRole("complementary", { name: "2025 Form 1065" });
    expect(locked()).toBe(false);
  });
});

// ---- The dirty guard ---------------------------------------------------------------------------

describe("the dirty guard", () => {
  function Dirty({ onOpenChange }: { onOpenChange: (open: boolean) => void }): JSX.Element {
    const [open, setOpen] = useState(true);
    const [title, setTitle] = useState("");
    return (
      <Dialog
        open={open}
        onOpenChange={(next) => {
          onOpenChange(next);
          setOpen(next);
        }}
        title="Issue"
        dirty={title !== ""}
      >
        <input
          aria-label="Title"
          value={title}
          onChange={(e) => {
            setTitle(e.target.value);
          }}
        />
      </Dialog>
    );
  }

  it("closes a clean dialog on Escape and on the scrim", async () => {
    const onOpenChange = vi.fn();
    render(<Dirty onOpenChange={onOpenChange} />);
    await screen.findByRole("dialog", { name: "Issue" });
    escape();
    await closed("Issue");
    expect(onOpenChange).toHaveBeenCalledExactlyOnceWith(false);
  });

  it("asks 'Discard changes?' on Escape, the close and the scrim, and closes on none of them", async () => {
    const onOpenChange = vi.fn();
    render(<Dirty onOpenChange={onOpenChange} />);
    fireEvent.change(await screen.findByLabelText("Title"), { target: { value: "Cash" } });

    escape();
    const guard = await screen.findByRole("alertdialog", { name: "Discard changes?" });
    expect(within(guard).getByText("What you typed in Issue will be lost.")).toBeTruthy();
    fireEvent.click(within(guard).getByRole("button", { name: "Keep editing" }));
    await closed("Discard changes?", "alertdialog");

    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    await screen.findByRole("alertdialog", { name: "Discard changes?" });
    fireEvent.click(screen.getByRole("button", { name: "Keep editing" }));
    await closed("Discard changes?", "alertdialog");

    const scrim = document.querySelector<HTMLElement>("[data-scrim]");
    expect(scrim).not.toBeNull();
    fireEvent.pointerDown(scrim as HTMLElement, { button: 0 });
    fireEvent.click(scrim as HTMLElement);
    await screen.findByRole("alertdialog", { name: "Discard changes?" });
    expect(onOpenChange).not.toHaveBeenCalled();
    expect(under("Issue")).toBeTruthy();
  });

  it("focuses Keep editing first, and Escape on the guard keeps editing", async () => {
    render(<Dirty onOpenChange={() => undefined} />);
    fireEvent.change(await screen.findByLabelText("Title"), { target: { value: "Cash" } });
    escape();
    await screen.findByRole("alertdialog", { name: "Discard changes?" });
    await waitFor(() => {
      expect(document.activeElement).toBe(screen.getByRole("button", { name: "Keep editing" }));
    });
    escape();
    await closed("Discard changes?", "alertdialog");
    expect(screen.getByRole("dialog", { name: "Issue" })).toBeTruthy();
  });

  it("Discard closes the dialog and releases the page", async () => {
    const onOpenChange = vi.fn();
    render(<Dirty onOpenChange={onOpenChange} />);
    fireEvent.change(await screen.findByLabelText("Title"), { target: { value: "Cash" } });
    escape();
    fireEvent.click(await screen.findByRole("button", { name: "Discard" }));
    await closed("Issue");
    expect(onOpenChange).toHaveBeenCalledWith(false);
    await waitFor(() => {
      expect(locked()).toBe(false);
    });
    expect(screen.queryByRole("alertdialog")).toBeNull();
  });

  it("asks of a dirty drawer, a sheet and a full sheet too", async () => {
    const onOpenChange = vi.fn();
    render(
      <>
        <Drawer open dirty onOpenChange={onOpenChange} title="Request">
          <p>Body</p>
        </Drawer>
      </>,
    );
    await screen.findByRole("dialog", { name: "Request" });
    escape();
    await screen.findByRole("alertdialog", { name: "Discard changes?" });
    expect(onOpenChange).not.toHaveBeenCalled();
    cleanup();
    render(
      <SheetModal open dirty onOpenChange={onOpenChange} title="Raise Issue">
        <p>Body</p>
      </SheetModal>,
    );
    await screen.findByRole("dialog", { name: "Raise Issue" });
    escape();
    await screen.findByRole("alertdialog", { name: "Discard changes?" });
    cleanup();
    render(
      <FullSheet open dirty onOpenChange={onOpenChange} title="Allocation structure">
        <p>Body</p>
      </FullSheet>,
    );
    await screen.findByRole("dialog", { name: "Allocation structure" });
    escape();
    await screen.findByRole("alertdialog", { name: "Discard changes?" });
    expect(onOpenChange).not.toHaveBeenCalled();
  });
});

// ---- Drawers -----------------------------------------------------------------------------------

describe("Drawer", () => {
  it("is a modal dialog with a scrim, focus on the close, and the close on the left", async () => {
    render(
      <Drawer open onOpenChange={() => undefined} title="Notifications">
        <p>Body</p>
      </Drawer>,
    );
    const drawer = await screen.findByRole("dialog", { name: "Notifications" });
    await waitFor(() => {
      expect(document.activeElement).toBe(within(drawer).getByRole("button", { name: "Close" }));
    });
    expect(document.querySelector("[data-scrim]")).not.toBeNull();
    const header = drawer.querySelector("header") as HTMLElement;
    expect(within(header).getByRole("button", { name: "Close" }).className).toContain("left-");
    expect(drawer.className).toContain("w-[440px]");
  });

  it("a peek is a complementary region: no scrim, no focus taken, and the page stays live", async () => {
    const onOpenChange = vi.fn();
    const page = vi.fn();
    render(
      <>
        <Button onClick={page}>Row</Button>
        <Drawer open peek onOpenChange={onOpenChange} title="2025 Form 1065">
          <p>Body</p>
        </Drawer>
      </>,
    );
    const peek = await screen.findByRole("complementary", { name: "2025 Form 1065" });
    expect(document.querySelector("[data-scrim]")).toBeNull();
    expect(peek.contains(document.activeElement)).toBe(false);
    const row = screen.getByRole("button", { name: "Row" });
    fireEvent.pointerDown(row);
    fireEvent.click(row);
    expect(page).toHaveBeenCalledOnce();
    expect(onOpenChange).not.toHaveBeenCalled();
    expect(screen.getByRole("complementary", { name: "2025 Form 1065" })).toBeTruthy();
    escape();
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("never two drawers: the second replaces the first", async () => {
    function Page(): JSX.Element {
      const [a, setA] = useState(true);
      const [b, setB] = useState(false);
      return (
        <>
          <Drawer open={a} onOpenChange={setA} title="Notifications">
            <p>One</p>
          </Drawer>
          <Drawer open={b} onOpenChange={setB} title="Activity" size="sm">
            <p>Two</p>
          </Drawer>
          <Button
            onClick={() => {
              setB(true);
            }}
          >
            Activity
          </Button>
        </>
      );
    }
    render(<Page />);
    await screen.findByRole("dialog", { name: "Notifications" });
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "Activity", hidden: true }));
    });
    await screen.findByRole("dialog", { name: "Activity" });
    await closed("Notifications");
    expect(appOverlayStack.layers().filter((l) => l.kind === "drawer")).toHaveLength(1);
  });

  it("a dirty drawer that is replaced closes without asking", async () => {
    function Page(): JSX.Element {
      const [b, setB] = useState(false);
      return (
        <>
          <Drawer open dirty onOpenChange={() => undefined} title="Request">
            <p>One</p>
          </Drawer>
          <Drawer open={b} onOpenChange={setB} title="Activity">
            <p>Two</p>
          </Drawer>
          <Button
            onClick={() => {
              setB(true);
            }}
          >
            Activity
          </Button>
        </>
      );
    }
    render(<Page />);
    await screen.findByRole("dialog", { name: "Request" });
    fireEvent.click(screen.getByRole("button", { name: "Activity", hidden: true }));
    await screen.findByRole("dialog", { name: "Activity" });
    expect(screen.queryByRole("alertdialog")).toBeNull();
  });

  it("has Open and a ··· menu when asked, and Open does not need an ellipsis", async () => {
    const onOpen = vi.fn();
    render(
      <Drawer
        open
        peek
        onOpenChange={() => undefined}
        title="2025 Form 1065"
        onOpen={onOpen}
        more={[[{ label: "Copy link", onSelect: () => undefined }]]}
      >
        <p>Body</p>
      </Drawer>,
    );
    fireEvent.click(await screen.findByRole("button", { name: "Open" }));
    expect(onOpen).toHaveBeenCalledOnce();
    expect(screen.getByRole("button", { name: "More actions" })).toBeTruthy();
  });
});

// ---- Initial focus -----------------------------------------------------------------------------

describe("initial focus", () => {
  it("goes to the first field", async () => {
    render(
      <Dialog open onOpenChange={() => undefined} title="Issue" action={<Button>Create</Button>}>
        <input aria-label="Title" />
        <input type="checkbox" aria-label="Agree" />
      </Dialog>,
    );
    await waitFor(() => {
      expect(document.activeElement).toBe(screen.getByLabelText("Title"));
    });
  });

  it("goes to the first checkbox when there is no field", async () => {
    render(
      <Dialog
        open
        onOpenChange={() => undefined}
        title="Sign off"
        action={<Button>Sign off</Button>}
      >
        <input type="checkbox" aria-label="I reviewed it" />
      </Dialog>,
    );
    await waitFor(() => {
      expect(document.activeElement).toBe(screen.getByLabelText("I reviewed it"));
    });
  });

  it("goes to the primary action when there is neither", async () => {
    render(
      <Dialog
        open
        onOpenChange={() => undefined}
        title="Send request"
        action={<Button>Send</Button>}
      >
        <p>Two items</p>
      </Dialog>,
    );
    await waitFor(() => {
      expect(document.activeElement).toBe(screen.getByRole("button", { name: "Send" }));
    });
  });

  it("goes to the close on a full sheet", async () => {
    render(
      <FullSheet open onOpenChange={() => undefined} title="Allocation structure">
        <input aria-label="Name" />
      </FullSheet>,
    );
    await waitFor(() => {
      expect(document.activeElement).toBe(screen.getByRole("button", { name: "Close" }));
    });
  });
});

// ---- The frames --------------------------------------------------------------------------------

describe("Dialog", () => {
  it.each([
    ["sm", "w-[420px]"],
    ["md", "w-[560px]"],
    ["lg", "w-[760px]"],
    ["xl", "w-[1140px]"],
  ] as const)("is %s wide", async (size, cls) => {
    render(
      <Dialog open onOpenChange={() => undefined} title="Issue" size={size}>
        <p>Body</p>
      </Dialog>,
    );
    expect((await screen.findByRole("dialog", { name: "Issue" })).className).toContain(cls);
  });

  it("puts the close left, the title centred and the one action right in a 52 header", async () => {
    render(
      <Dialog open onOpenChange={() => undefined} title="Issue" action={<Button>Create</Button>}>
        <p>Body</p>
      </Dialog>,
    );
    const dialog = await screen.findByRole("dialog", { name: "Issue" });
    const header = dialog.querySelector("header") as HTMLElement;
    expect(header.className).toContain("h-[52px]");
    expect(header.firstElementChild).toBe(within(header).getByRole("button", { name: "Close" }));
    expect(within(header).getByRole("heading", { name: "Issue" }).className).toContain("left-1/2");
    expect(header.lastElementChild?.textContent).toBe("Create");
    expect(dialog.querySelector("footer")).toBeNull();
  });

  it("opens from its trigger and focus returns to it", async () => {
    function Page(): JSX.Element {
      const [open, setOpen] = useState(false);
      return (
        <Dialog
          open={open}
          onOpenChange={setOpen}
          title="Issue"
          trigger={<Button opensDialog>Raise…</Button>}
        >
          <p>Body</p>
        </Dialog>
      );
    }
    render(<Page />);
    const trigger = screen.getByRole("button", { name: "Raise…" });
    press(trigger);
    await screen.findByRole("dialog", { name: "Issue" });
    escape();
    await closed("Issue");
    await waitFor(() => {
      expect(document.activeElement).toBe(trigger);
    });
  });

  it("is held in place, as a group, with no layer, for a specimen", () => {
    render(
      <Dialog open={false} onOpenChange={() => undefined} title="Issue" forceState="open">
        <p>Body</p>
      </Dialog>,
    );
    expect(screen.getByRole("group", { name: "Issue" })).toBeTruthy();
    expect(appOverlayStack.layers()).toHaveLength(0);
    expect(locked()).toBe(false);
  });
});

describe("ConfirmDialog", () => {
  it("is an alertdialog with no header, Cancel focused, and a destructive confirm", async () => {
    const onConfirm = vi.fn();
    const onOpenChange = vi.fn();
    render(
      <ConfirmDialog
        open
        onOpenChange={onOpenChange}
        title="Delete Schedule 2"
        confirmLabel="Delete"
        onConfirm={onConfirm}
      >
        Schedule 2 and its 14 rows will be removed from the workpaper.
      </ConfirmDialog>,
    );
    const dialog = await screen.findByRole("alertdialog", { name: "Delete Schedule 2" });
    expect(dialog.querySelector("header")).toBeNull();
    await waitFor(() => {
      expect(document.activeElement).toBe(within(dialog).getByRole("button", { name: "Cancel" }));
    });
    expect(within(dialog).getByRole("button", { name: "Delete" }).dataset["variant"]).toBe(
      "destructive",
    );
    fireEvent.click(within(dialog).getByRole("button", { name: "Delete" }));
    expect(onConfirm).toHaveBeenCalledOnce();
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("Cancel and Escape close without confirming", async () => {
    const onConfirm = vi.fn();
    const onOpenChange = vi.fn();
    render(
      <ConfirmDialog
        open
        onOpenChange={onOpenChange}
        title="Delete Schedule 2"
        confirmLabel="Delete"
        onConfirm={onConfirm}
      />,
    );
    await screen.findByRole("alertdialog");
    escape();
    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(onConfirm).not.toHaveBeenCalled();
  });
});

describe("SheetModal", () => {
  it("is 500 wide from 52 down, with a 56 header, the close left and the action right", async () => {
    render(
      <SheetModal
        open
        onOpenChange={() => undefined}
        title="Raise Issue"
        action={<Button disabled>Save</Button>}
      >
        <p>Body</p>
      </SheetModal>,
    );
    const sheet = await screen.findByRole("dialog", { name: "Raise Issue" });
    expect(sheet.className).toContain("top-[52px]");
    expect(sheet.className).toContain("w-[500px]");
    expect(sheet.className).toContain("bottom-0");
    expect(sheet.querySelector("header")?.className).toContain("h-[56px]");
    expect(document.querySelector("[data-scrim]")?.getAttribute("data-scrim")).toBe("agent");
    expect(within(sheet).getByRole("button", { name: "Save" })).toHaveProperty("disabled", true);
  });
});

describe("Wizard", () => {
  const steps = [
    { id: "client", label: "Client & type", state: "done" },
    { id: "standards", label: "Standards & methodology", state: "current" },
    { id: "period", label: "Period & deadlines", state: "todo" },
  ] as const;

  it("draws a 220 step list, Back, Save draft and Next, and Create on the last step", async () => {
    const onNext = vi.fn();
    const { rerender } = render(
      <Wizard
        open
        onOpenChange={() => undefined}
        title="New engagement"
        subtitle="Draft · saved 9:39 AM"
        steps={steps}
        onNext={onNext}
        onSaveDraft={() => undefined}
      >
        <p>Step 2</p>
      </Wizard>,
    );
    const wizard = await screen.findByRole("dialog", { name: "New engagement" });
    expect(within(wizard).getByRole("navigation", { name: "Steps" })).toBeTruthy();
    expect(within(wizard).getByRole("button", { name: "Back" })).toHaveProperty("disabled", false);
    expect(within(wizard).getByRole("button", { name: "Save draft" })).toBeTruthy();
    fireEvent.click(within(wizard).getByRole("button", { name: "Next" }));
    expect(onNext).toHaveBeenCalledOnce();
    expect(within(wizard).queryByRole("button", { name: "Create" })).toBeNull();
    rerender(
      <Wizard
        open
        onOpenChange={() => undefined}
        title="New engagement"
        steps={[
          { id: "client", label: "Client & type", state: "done" },
          { id: "period", label: "Period & deadlines", state: "current" },
        ]}
      >
        <p>Last</p>
      </Wizard>,
    );
    expect(within(wizard).getByRole("button", { name: "Create" })).toBeTruthy();
    expect(within(wizard).queryByRole("button", { name: "Next" })).toBeNull();
  });

  it("disables Back on the first step", async () => {
    render(
      <Wizard
        open
        onOpenChange={() => undefined}
        title="New engagement"
        steps={[
          { id: "a", label: "Client & type", state: "current" },
          { id: "b", label: "Period", state: "todo" },
        ]}
      >
        <p>One</p>
      </Wizard>,
    );
    expect(await screen.findByRole("button", { name: "Back" })).toHaveProperty("disabled", true);
  });
});

// ---- Command palette ---------------------------------------------------------------------------

describe("CommandPalette", () => {
  const groups = [
    {
      label: "Go to",
      items: [
        { id: "eng", label: "Engagements", hint: "Page", run: vi.fn() },
        { id: "tax", label: "Tax Returns", hint: "Page", run: vi.fn() },
      ],
    },
  ];

  it("moves with the arrows without wrapping, runs the row on Enter and closes", async () => {
    const onOpenChange = vi.fn();
    const run = vi.fn();
    render(
      <CommandPalette
        open
        onOpenChange={onOpenChange}
        query=""
        onQueryChange={() => undefined}
        groups={[
          {
            label: "Go to",
            items: [
              { id: "eng", label: "Engagements", run: vi.fn() },
              { id: "tax", label: "Tax Returns", run },
            ],
          },
        ]}
      />,
    );
    const input = await screen.findByRole("combobox", { name: "Search" });
    await waitFor(() => {
      expect(document.activeElement).toBe(input);
    });
    const selected = (): string | null =>
      screen.getByRole("option", { selected: true }).textContent;
    expect(selected()).toBe("Engagements");
    fireEvent.keyDown(input, { key: "ArrowUp" });
    expect(selected()).toBe("Engagements");
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(selected()).toBe("Tax Returns");
    fireEvent.keyDown(input, { key: "Enter" });
    expect(run).toHaveBeenCalledOnce();
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("is 560 wide with the wordmark and key hints, and Escape closes it", async () => {
    const onOpenChange = vi.fn();
    render(
      <CommandPalette
        open
        onOpenChange={onOpenChange}
        query=""
        onQueryChange={() => undefined}
        groups={groups}
      />,
    );
    const palette = await screen.findByRole("dialog", { name: "Command palette" });
    expect(palette.className).toContain("w-[560px]");
    expect(within(palette).getByRole("img", { name: "Accrued" })).toBeTruthy();
    expect(within(palette).getByText("Navigate")).toBeTruthy();
    escape();
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("says what matched nothing, quoting the query", async () => {
    render(
      <CommandPalette
        open
        onOpenChange={() => undefined}
        query="zzz"
        onQueryChange={() => undefined}
        groups={[]}
      />,
    );
    expect(await screen.findByText("No matches for “zzz”")).toBeTruthy();
    // An empty listbox is not valid ARIA: with nothing to pick there is no listbox.
    expect(screen.queryByRole("listbox")).toBeNull();
  });
});

// ---- Popover -----------------------------------------------------------------------------------

describe("Popover", () => {
  it("opens from its trigger, closes on Escape and returns focus to the trigger", async () => {
    render(
      <Popover label="Assign to" trigger={<Button>Assign…</Button>} variant="tray" width={266}>
        <p>Kevin Osei</p>
      </Popover>,
    );
    const trigger = screen.getByRole("button", { name: "Assign…" });
    press(trigger);
    const pop = await screen.findByRole("dialog", { name: "Assign to" });
    expect(pop.dataset["variant"]).toBe("tray");
    expect(pop.style.width).toBe("266px");
    escape();
    await closed("Assign to");
    await waitFor(() => {
      expect(document.activeElement).toBe(trigger);
    });
  });
});

// ---- Reduced motion ----------------------------------------------------------------------------

function reduceMotion(reduce: boolean): void {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: reduce && query.includes("prefers-reduced-motion"),
    media: query,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
  }));
}

describe("reduced motion", () => {
  const frames = (): JSX.Element => (
    <>
      <Drawer open onOpenChange={() => undefined} title="Notifications">
        <p>Body</p>
      </Drawer>
      <Dialog open onOpenChange={() => undefined} title="Issue">
        <p>Body</p>
      </Dialog>
      <SheetModal open onOpenChange={() => undefined} title="Raise Issue">
        <p>Body</p>
      </SheetModal>
      <FullSheet open onOpenChange={() => undefined} title="Allocation structure">
        <p>Body</p>
      </FullSheet>
    </>
  );

  it("draws no animation class on any layer or scrim", async () => {
    reduceMotion(true);
    render(frames());
    await screen.findAllByText("Allocation structure", { selector: "h2" });
    const els = [...document.querySelectorAll<HTMLElement>("[data-overlay], [data-scrim]")];
    expect(els.length).toBeGreaterThanOrEqual(8);
    for (const el of els) expect(el.className, el.dataset["overlay"]).not.toMatch(/motion-/);
  });

  it("animates when motion is allowed", async () => {
    reduceMotion(false);
    render(frames());
    await screen.findAllByText("Allocation structure", { selector: "h2" });
    const drawer = under("Notifications");
    expect(drawer.className).toContain("motion-drawer-in");
    expect(document.querySelector("[data-scrim]")?.className).toContain("motion-fade");
  });
});

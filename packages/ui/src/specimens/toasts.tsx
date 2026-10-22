import type { JSX } from "react";
import { Button } from "../components/button";
import { Toast, ToastHost } from "../components/toast";
import { createToast, createToastStore } from "../components/toast-store";
import { Held, Row, Sheet } from "./frame";

// C-21 Toast (F-05-T21). The kinds as static specimens, then a live board on the window's store:
// the stack holding at three, Undo, a running toast settling in place, and hover to pause. Copy is
// the kit's own examples (C-21 §5). The board has its own store, so the app's host never doubles it.

const board = createToastStore();
const toast = createToast(board);

export function ToastKindsSpecimen(): JSX.Element {
  return (
    <Sheet title="Toast kinds" meta="36h · espresso · 13/500 · e3">
      <Row name="success" meaning="A user action is done" spec="green disc · status, polite">
        <Toast kind="success" text="Approved 3 adjustments" still />
        <Held name="with action">
          <Toast kind="success" text="Filed to 2025 Binder · Income" action="Undo" still />
        </Held>
      </Row>
      <Row name="info" meaning="Something the user may open" spec="Info 15 at .72">
        <Toast kind="info" text="Reply sent to Matthew Douglas" action="View" still />
      </Row>
      <Row name="warning" meaning="Done, with something to look at" spec="disc amber · !">
        <Toast
          kind="warning"
          text="Uploaded 3 of 4 files · 1 was over 25 MB"
          action="View"
          still
        />
      </Row>
      <Row
        name="error"
        meaning="A background failure to retry or ignore; never a blocking error"
        spec="disc red · alert, assertive · close on"
      >
        <Toast kind="error" text="Couldn’t connect to Cascadia Bank" action="Retry" still />
      </Row>
      <Row name="running" meaning="A background job; persists until updated" spec="14px spinner">
        <Toast kind="running" text="Uploading 4 files…" still />
        <Held name="with close">
          <Toast kind="running" text="Uploading 4 files…" close still />
        </Held>
      </Row>
    </Sheet>
  );
}

function fire(): void {
  toast.show({ text: "Bank Reconciliation installed" });
}

function upload(): void {
  const job = toast.running("Uploading 4 files…");
  setTimeout(() => {
    job.update({
      kind: "warning",
      text: "Uploaded 3 of 4 files · 1 was over 25 MB",
      action: "View",
    });
  }, 1600);
}

function connect(): void {
  toast.show({
    kind: "error",
    text: "Couldn’t connect to Cascadia Bank",
    action: "Retry",
    onAction: () => {
      const job = toast.running("Connecting to Cascadia Bank…");
      setTimeout(() => {
        job.succeed("Connected Cascadia Bank");
      }, 1400);
    },
  });
}

function undoable(): void {
  toast.undoable({ text: "Approved 3 adjustments", undo: () => undefined });
}

export function ToastLiveSpecimen(): JSX.Element {
  return (
    <Sheet title="Live stack" meta="4 s · 8 s with an action · at most 3 · hover pauses">
      <div className="relative flex h-[260px] flex-col gap-3 bg-shell p-4">
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" size="sm" onClick={fire}>
            Show a toast
          </Button>
          <Button variant="secondary" size="sm" onClick={undoable}>
            Show an Undo toast
          </Button>
          <Button variant="secondary" size="sm" onClick={upload}>
            Upload 4 files
          </Button>
          <Button variant="secondary" size="sm" onClick={connect}>
            Connect Cascadia Bank
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              toast.clear();
            }}
          >
            Clear all
          </Button>
        </div>
        <ToastHost contained store={board} />
      </div>
    </Sheet>
  );
}

// N-01-T23: inside the firm shell INB-01 passes no toolbar, so InboxLayout draws its filter bar and
// columns without a second window (as RecordCockpit's bare mode does); with a toolbar it is the
// framed T8 window as before.
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { InboxLayout } from "./inbox-layout";

afterEach(cleanup);

const props = {
  filters: <span>23 waiting</span>,
  rail: { body: <p>rows</p> },
  reading: { body: <p>message</p> },
};

describe("InboxLayout bare", () => {
  it("draws no toolbar and no window without a toolbar", () => {
    const { container } = render(<InboxLayout {...props} />);
    expect(container.querySelector("[data-inbox='bare']")).not.toBeNull();
    expect(container.querySelector("[data-shell='app']")).toBeNull();
    expect(container.querySelector("[data-inbox='filters']")?.textContent).toBe("23 waiting");
    expect(container.querySelector("[data-inbox='rail']")?.textContent).toContain("rows");
  });
});

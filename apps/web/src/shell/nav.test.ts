// F-02-T09 (D1): the bar holds the 13 areas of scope-guards.yaml, in order, with no badge or count.
import { describe, expect, it } from "vitest";
import { NAV } from "./nav";

describe("the firm bar", () => {
  it("has the 13 areas in chapter 04 order", () => {
    expect(NAV.map((i) => i.label)).toEqual([
      "Home",
      "Engagements",
      "Tax Returns",
      "Files",
      "Knowledge",
      "Workbench",
      "Inbox",
      "Clients",
      "Binders",
      "Notices",
      "Audits",
      "Closes",
      "Signatures",
    ]);
  });

  it("never carries a badge or a count", () => {
    for (const item of NAV) {
      expect(Object.keys(item)).toEqual(["label"]);
    }
  });
});

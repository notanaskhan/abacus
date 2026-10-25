// P-09-T06 (TASK-5004): AgentBlocks renders nodes only; facts through format.ts; markup inert.
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { AgentBlocks, AgentProse, factText } from "./blocks";

afterEach(cleanup);

const FACTS = {
  tb_total: { kind: "money", value: "16812400.00" },
  participants: { kind: "count", value: "286" },
} as const;

describe("AgentBlocks", () => {
  it("renders facts through format.ts, never the raw value or id", () => {
    expect(factText(FACTS.tb_total)).toBe("$16,812,400.00");
    expect(factText(FACTS.participants)).toBe("286");
    expect(factText(undefined)).toBe("—");
  });

  it("renders every part kind as nodes", () => {
    const { container } = render(
      <AgentBlocks
        facts={FACTS}
        blocks={{
          parts: [
            {
              kind: "p",
              segments: [
                { kind: "text", text: "Net trust assets are " },
                { kind: "fact", fact_id: "tb_total" },
                { kind: "cite", citation_id: "c1", n: 1 },
              ],
            },
            { kind: "metric", label: "Participants", fact_id: "participants" },
            { kind: "badge", object: "engagement", code: "active" },
            { kind: "kv", rows: [{ label: "Read", value: [{ kind: "text", text: "Census" }] }] },
            {
              kind: "options",
              options: [
                { key: "run", title: "Run the plan", recommended: true },
                { key: "change", title: "Change the order" },
              ],
            },
            { kind: "entity_ref", record_type: "work_paper", record_id: "w1" },
          ],
        }}
      />,
    );
    expect(screen.getByText("$16,812,400.00")).toBeTruthy();
    expect(screen.getByText("286")).toBeTruthy();
    expect(screen.getByText("Active")).toBeTruthy();
    expect(screen.getByText("Run the plan")).toBeTruthy();
    expect(screen.getByText("work paper")).toBeTruthy();
    expect(container.querySelector("sup")?.textContent).toBe("1");
  });

  it("renders markup as inert text and unknown parts as a neutral row", () => {
    const { container } = render(
      <AgentBlocks
        facts={{}}
        blocks={{
          parts: [
            { kind: "p", segments: [{ kind: "text", text: "<img src=x onerror=alert(1)>" }] },
            { kind: "html", html: "<script>x</script>" } as { kind: string },
          ],
        }}
      />,
    );
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("script")).toBeNull();
    expect(screen.getByText("This part can't be shown.")).toBeTruthy();
  });

  it("AgentProse renders one paragraph by the same rules", () => {
    render(
      <AgentProse
        facts={FACTS}
        segments={[
          { kind: "text", text: "Read " },
          { kind: "fact", fact_id: "participants" },
          { kind: "text", text: " participants" },
        ]}
      />,
    );
    expect(screen.getByText("286")).toBeTruthy();
  });
});

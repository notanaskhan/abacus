import { AGENT_TEXT_LIMIT, AgentText, sanitiseAgentText } from "@abacus/ui";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

afterEach(cleanup);

describe("ac18 sanitiseAgentText", () => {
  it("removes C0 and C1 controls but keeps newline and tab", () => {
    expect(sanitiseAgentText("a\u0000b\u0007c\u001Bd\u007Fe\u0085f\u009Fg")).toBe("abcdefg");
    expect(sanitiseAgentText("one\ntwo\tthree")).toBe("one\ntwo\tthree");
  });

  it("removes bidirectional overrides, embeddings and isolates", () => {
    const marks = ["‪", "‫", "‬", "‭", "‮", "⁦", "⁧", "⁨", "⁩"];
    for (const mark of marks) {
      expect(sanitiseAgentText(`ab${mark}cd`)).toBe("abcd");
    }
  });

  it("removes zero-width characters and the byte-order mark", () => {
    expect(sanitiseAgentText("a​b‌c‍d⁠e﻿f")).toBe("abcdef");
  });

  it("normalises CRLF to LF", () => {
    expect(sanitiseAgentText("a\r\nb\r\nc\nd")).toBe("a\nb\nc\nd");
  });

  it("leaves ordinary text, including non-Latin text, unchanged", () => {
    expect(sanitiseAgentText("Cash — 100 € 現金")).toBe("Cash — 100 € 現金");
  });

  it("truncates to 2000 code points plus an ellipsis", () => {
    expect(AGENT_TEXT_LIMIT).toBe(2000);
    expect(sanitiseAgentText("x".repeat(2000))).toBe("x".repeat(2000));
    expect(sanitiseAgentText("x".repeat(2001))).toBe(`${"x".repeat(2000)}…`);
  });

  it("counts code points, not UTF-16 units, when truncating", () => {
    const out = sanitiseAgentText("😀".repeat(2001));
    expect(Array.from(out)).toHaveLength(2001);
    expect(out.endsWith("😀…")).toBe(true);
  });
});

describe("ac18 AgentText", () => {
  it("renders hostile HTML as visible text, not elements", () => {
    const hostile = '<img src=x onerror="alert(1)"><script>alert(2)</script>';
    const { container } = render(<AgentText text={hostile} />);
    expect(screen.getByText(hostile)).toBeTruthy();
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("script")).toBeNull();
  });

  it("does not turn URLs into links", () => {
    const { container } = render(
      <AgentText text="See https://evil.example/pay and [x](https://evil.example)" />,
    );
    expect(container.querySelector("a")).toBeNull();
    expect(container.textContent).toContain("https://evil.example/pay");
  });

  it("strips disguising characters before rendering", () => {
    const { container } = render(<AgentText text={"pay‮evil​\u0000 now"} />);
    expect(container.textContent).toBe("payevil now");
  });

  it("renders inline text in a span and keeps line breaks in a block", () => {
    const { container } = render(
      <>
        <AgentText inline text="quote" />
        <AgentText text={"line one\nline two"} />
      </>,
    );
    expect(container.querySelector("span")?.textContent).toBe("quote");
    expect(container.querySelector("p")?.textContent).toBe("line one\nline two");
  });

  it("caps the length of what it renders", () => {
    const { container } = render(<AgentText text={"y".repeat(5000)} />);
    expect(container.textContent).toBe(`${"y".repeat(2000)}…`);
  });
});

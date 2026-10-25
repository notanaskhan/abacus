// Writes parity-report/parity.json: artboard -> diff % -> tier, one row per parity test that ran
// (F-05-T16; chapter 04 §9.3). parity.spec.ts attaches each row as a "parity" annotation.
// F-04-T33: screens.spec.ts attaches "parity-screen" rows, written to parity-report/screens/
// as parity.json and index.html (artboard -> diff % -> tier -> locked).
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import type { Reporter, TestCase, TestResult } from "@playwright/test/reporter";
import { renderHtml, type ScreenResult } from "../parity/screen-rows";

interface Row {
  artboard: string;
  tier: string;
  gate: string;
  diffPercent: number | null;
  size: string;
  deviation: string | null;
  note: string | null;
  status: string;
}

class ParityReporter implements Reporter {
  private readonly rows: Row[] = [];
  private readonly screens: ScreenResult[] = [];
  private missing: string[] = [];

  onTestEnd(test: TestCase, result: TestResult): void {
    for (const annotation of test.annotations) {
      if (annotation.type === "parity-screen-missing" && annotation.description !== undefined) {
        this.missing = JSON.parse(annotation.description) as string[];
        continue;
      }
      if (annotation.type === "parity-screen" && annotation.description !== undefined) {
        this.screens.push(JSON.parse(annotation.description) as ScreenResult);
        continue;
      }
      if (annotation.type !== "parity" || annotation.description === undefined) continue;
      const row = JSON.parse(annotation.description) as Omit<Row, "status">;
      this.rows.push({ ...row, status: result.status });
    }
  }

  onEnd(): void {
    this.writeScreens();
    if (this.rows.length === 0) return;
    mkdirSync("parity-report", { recursive: true });
    const rows = [...this.rows].sort((a, b) => a.artboard.localeCompare(b.artboard));
    writeFileSync("parity-report/parity.json", `${JSON.stringify({ rows }, null, 2)}\n`, "utf8");
  }

  private writeScreens(): void {
    if (this.screens.length === 0) return;
    const version = readFileSync("../../docs/design/HANDOFF_VERSION", "utf8").trim();
    const rows = [...this.screens].sort((a, b) => a.artboard.localeCompare(b.artboard));
    mkdirSync("parity-report/screens", { recursive: true });
    writeFileSync(
      "parity-report/screens/parity.json",
      `${JSON.stringify({ handoff_version: version, rows, missing: this.missing }, null, 2)}\n`,
      "utf8",
    );
    writeFileSync(
      "parity-report/screens/index.html",
      renderHtml(rows, version, this.missing),
      "utf8",
    );
  }
}

export default ParityReporter;

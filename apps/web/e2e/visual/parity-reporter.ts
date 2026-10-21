// Writes parity-report/parity.json: artboard -> diff % -> tier, one row per parity test that ran
// (F-05-T16; chapter 04 §9.3). parity.spec.ts attaches each row as a "parity" annotation.
import { mkdirSync, writeFileSync } from "node:fs";
import type { Reporter, TestCase, TestResult } from "@playwright/test/reporter";

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

  onTestEnd(test: TestCase, result: TestResult): void {
    for (const annotation of test.annotations) {
      if (annotation.type !== "parity" || annotation.description === undefined) continue;
      const row = JSON.parse(annotation.description) as Omit<Row, "status">;
      this.rows.push({ ...row, status: result.status });
    }
  }

  onEnd(): void {
    if (this.rows.length === 0) return;
    mkdirSync("parity-report", { recursive: true });
    const rows = [...this.rows].sort((a, b) => a.artboard.localeCompare(b.artboard));
    writeFileSync("parity-report/parity.json", `${JSON.stringify({ rows }, null, 2)}\n`, "utf8");
  }
}

export default ParityReporter;

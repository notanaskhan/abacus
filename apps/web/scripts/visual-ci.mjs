// CI's visual run (F-05-T17; chapter 04 §9.3): the gallery screenshot regression against the pull
// request's base commit, then every visual test against the head.
//
//   BASE_SHA=<base commit> node scripts/visual-ci.mjs        (from apps/web; `pnpm visual:ci`)
//
// The regression baselines are not committed. This renders the specimens from the base commit on
// this runner (so fonts and anti-aliasing match), restores the head, and compares. A specimen the
// base does not have is new and is listed, not failed. Without a usable base (a push, a base that
// predates the gallery) there is nothing to compare, and the run is Tier D and parity only.
// Tier A parity and Tier D block; the regression blocks unless VISUAL_REGRESSION_BLOCKING=false (pushes).
//
// Node only, no dependencies. Git commands touch only packages/ui and apps/web/src, and refuse a
// dirty tree there unless CI is set.
import { execFileSync } from "node:child_process";

const SOURCE_PATHS = ["packages/ui", "apps/web/src"];
const GALLERY_ENTRY = "apps/web/src/gallery/pages.tsx";
const env = { ...process.env, ABACUS_VISUAL: "1" };

const repoRoot = execFileSync("git", ["rev-parse", "--show-toplevel"], {
  encoding: "utf8",
}).trim();

function git(...args) {
  return execFileSync("git", args, { encoding: "utf8", cwd: repoRoot }).trim();
}

function ok(...args) {
  try {
    git(...args);
    return true;
  } catch {
    return false;
  }
}

function playwright(...args) {
  execFileSync("pnpm", ["exec", "playwright", "test", "--project=visual", ...args], {
    stdio: "inherit",
    env,
  });
}

const base = process.env.BASE_SHA ?? "";
const usableBase =
  /^[0-9a-f]{40}$/.test(base) &&
  !/^0+$/.test(base) &&
  ok("cat-file", "-e", `${base}^{commit}`) &&
  ok("cat-file", "-e", `${base}:${GALLERY_ENTRY}`);

let regression = false;
if (usableBase) {
  if (process.env.CI === undefined && git("status", "--porcelain", "--", ...SOURCE_PATHS) !== "") {
    console.error(
      `visual-ci: ${SOURCE_PATHS.join(" and ")} have uncommitted changes; commit or stash.`,
    );
    process.exit(2);
  }
  const restore = (source) =>
    execFileSync(
      "git",
      ["restore", `--source=${source}`, "--staged", "--worktree", "--", ...SOURCE_PATHS],
      { cwd: repoRoot, stdio: "inherit" },
    );
  try {
    console.log(`visual-ci: rendering the baseline from ${base.slice(0, 12)}`);
    restore(base);
    playwright("regression", "--update-snapshots=all");
    regression = true;
  } finally {
    restore("HEAD");
  }
} else {
  console.log("visual-ci: no usable base commit; skipping the regression comparison");
}

// A regression diff blocks a pull request or the merge queue, where someone reviews the change. On a
// direct push to main the builder has already chosen the change, so the diff is reported (the
// artifact holds it) and only Tier D and parity block.
const blocking = process.env.VISUAL_REGRESSION_BLOCKING !== "false";
if (regression) {
  try {
    playwright("regression", "--update-snapshots=none");
  } catch (error) {
    if (blocking) throw error;
    console.log(
      "::warning::visual-ci: specimens changed against the base; see gallery-visual-report",
    );
  }
}
playwright("tier-d", "parity", "--update-snapshots=none");

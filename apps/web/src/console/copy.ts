// The console entry's own words (G-04-T14). The handoff draws no console sign-in frame (PLT-01's
// spec names none), so the gate borrows SHL-06's title and the action word SHL-06 uses for its
// retry; recorded with DEC-5528 as undesigned.
import { COPY as SHL06 } from "../screens/SHL-06/copy";

export const CONSOLE_COPY = {
  signIn: { title: SHL06.title, action: "Sign in" },
} as const;

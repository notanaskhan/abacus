// The workbench domain (W-02 §5.1): WB-01, WB-02 and WB-03 read and write sessions only through
// these hooks, over the generated client.
import "./realtime";

export * from "./mutations";
export * from "./queries";
export { workbenchTopics } from "./realtime";

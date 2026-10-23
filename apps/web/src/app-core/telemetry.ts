// Browser error reporting (Q-01-T50; Q-01 F6, chapter 06): `@sentry/browser` through the
// same-origin tunnel `POST /v1/telemetry/errors` (Q-01-T48), which re-scrubs by allowlist and
// forwards to Sentry. This side scrubs first, also by allowlist: an event leaves the browser with
// the error type, its stack frames (file path, function, line), the route template, release and
// environment, and nothing else. No breadcrumbs, no user, no URL or query string, no message
// text and no DOM text.
//
// Only a signed-in session reports: the transport sends the session's bearer token and drops the
// event when there is none (errors before sign-in are a documented gap; plan Q-01 Q1). Loaded
// lazily from main.tsx, only when the runtime config names a DSN and the tunnel.
import {
  type BrowserOptions,
  type ErrorEvent,
  type Exception,
  type StackFrame,
  createTransport,
  dedupeIntegration,
  globalHandlersIntegration,
  init,
  linkedErrorsIntegration,
} from "@sentry/browser";
import { type RuntimeConfig, telemetryTarget } from "./runtime-config";

export interface TelemetryHooks {
  /** The matched route's template (`/engagements/$engagementId`), never the URL itself. */
  routeTemplate: () => string | undefined;
  /** The signed-in session's request headers, or null when no one is signed in. */
  sessionHeaders: () => Record<string, string> | null;
}

type TransportFactory = NonNullable<BrowserOptions["transport"]>;

const ROUTE_TAG = "route";
const MAX_FRAMES = 50;
const MAX_EXCEPTIONS = 5;
const MAX_TEXT = 200;

function short(value: unknown): string | undefined {
  return typeof value === "string" && value.length > 0 ? value.slice(0, MAX_TEXT) : undefined;
}

/** A bundle file's path, without origin, query or fragment (the portal host can name a firm). */
export function framePath(filename: string | undefined): string | undefined {
  if (filename === undefined) return undefined;
  const bare = filename.split(/[?#]/, 1)[0] ?? "";
  const path = bare.replace(/^[a-z][a-z0-9+.-]*:\/\/[^/]*/i, "");
  return short(path);
}

function scrubFrame(frame: StackFrame): StackFrame {
  const out: StackFrame = {};
  const filename = framePath(frame.filename);
  if (filename !== undefined) out.filename = filename;
  const fn = short(frame.function);
  if (fn !== undefined) out.function = fn;
  if (typeof frame.lineno === "number") out.lineno = frame.lineno;
  if (typeof frame.colno === "number") out.colno = frame.colno;
  if (typeof frame.in_app === "boolean") out.in_app = frame.in_app;
  return out;
}

function scrubException(exception: Exception): Exception {
  // `value` (the message) is dropped: it can carry record data or text read from the page.
  const out: Exception = { type: short(exception.type) ?? "Error" };
  if (exception.mechanism !== undefined) {
    out.mechanism = { type: exception.mechanism.type };
    if (typeof exception.mechanism.handled === "boolean") {
      out.mechanism.handled = exception.mechanism.handled;
    }
  }
  const frames = exception.stacktrace?.frames;
  if (frames !== undefined) out.stacktrace = { frames: frames.slice(-MAX_FRAMES).map(scrubFrame) };
  return out;
}

/**
 * The allowlist: a new event built from the few fields that may leave the browser. Anything the
 * SDK or an integration adds later is dropped because it is never copied. Only errors are
 * reported: an event with no exception, or below `error` (a bare message), is dropped.
 */
export function scrubEvent(event: ErrorEvent, route: string | undefined): ErrorEvent | null {
  const exceptions = event.exception?.values ?? [];
  if (exceptions.length === 0) return null;
  if (event.level !== undefined && event.level !== "error" && event.level !== "fatal") return null;
  const out: ErrorEvent = {
    type: undefined,
    exception: { values: exceptions.slice(-MAX_EXCEPTIONS).map(scrubException) },
  };
  if (event.event_id !== undefined) out.event_id = event.event_id;
  if (event.timestamp !== undefined) out.timestamp = event.timestamp;
  if (event.platform !== undefined) out.platform = event.platform;
  if (event.level !== undefined) out.level = event.level;
  if (event.release !== undefined) out.release = event.release;
  if (event.environment !== undefined) out.environment = event.environment;
  const template = short(route);
  if (template !== undefined) out.tags = { [ROUTE_TAG]: template };
  return out;
}

/** Posts envelopes to the tunnel with the session's headers; drops them when signed out. */
function tunnelTransport(
  tunnel: string,
  sessionHeaders: TelemetryHooks["sessionHeaders"],
): TransportFactory {
  return (options) =>
    createTransport(options, async (request) => {
      const headers = sessionHeaders();
      if (headers === null) return {};
      // The tunnel takes a Sentry envelope, not a JSON body, so it is not a generated-client call.
      const response = await fetch(tunnel, {
        method: "POST",
        body: request.body as BodyInit,
        headers: { ...headers, "Content-Type": "application/x-sentry-envelope" },
        credentials: "same-origin",
        keepalive: true,
      });
      return {
        statusCode: response.status,
        headers: {
          "x-sentry-rate-limits": response.headers.get("x-sentry-rate-limits"),
          "retry-after": response.headers.get("retry-after"),
        },
      };
    });
}

/** The SDK options, or null when the runtime config leaves reporting off. */
export function telemetryOptions(
  config: RuntimeConfig,
  hooks: TelemetryHooks,
): BrowserOptions | null {
  const target = telemetryTarget(config);
  if (target === null) return null;
  return {
    dsn: target.dsn,
    tunnel: target.tunnel,
    transport: tunnelTransport(target.tunnel, hooks.sessionHeaders),
    release: config.release,
    environment: config.environment,
    // Uncaught errors and rejections only: no breadcrumbs, HTTP context, sessions or tracing.
    defaultIntegrations: false,
    integrations: [globalHandlersIntegration(), linkedErrorsIntegration(), dedupeIntegration()],
    maxBreadcrumbs: 0,
    beforeBreadcrumb: () => null,
    sendClientReports: false,
    dataCollection: {
      userInfo: false,
      cookies: false,
      httpHeaders: false,
      httpBodies: [],
      urlQueryParams: false,
      graphQL: { document: false, variables: false },
      genAI: { inputs: false, outputs: false },
      databaseQueryData: false,
      queues: false,
      stackFrameVariables: false,
      frameContextLines: 0,
    },
    beforeSend: (event) => scrubEvent(event, hooks.routeTemplate()),
  };
}

/** Start reporting if the runtime config allows it; true when the SDK was started. */
export function startTelemetry(config: RuntimeConfig, hooks: TelemetryHooks): boolean {
  const options = telemetryOptions(config, hooks);
  if (options === null) return false;
  init(options);
  return true;
}

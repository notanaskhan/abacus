// R-01's interim EmailPreview (R-01-T25; POR-20 a, c, d), until F-06-T16 re-homes the well onto
// T10e (`DocumentOnWell variant="email"`). It shows the server's deterministic rendering (`POST
// …/preview`) exactly as the client will receive it, and nothing else.
//
// Safety (ADR-052, ADR-064: template and client strings are hostile): the HTML goes into an
// `iframe` with an empty `sandbox` (no scripts, no forms, no same origin, no top navigation) and a
// Content-Security-Policy that forbids every fetch (`default-src 'none'`; inline styles only), so
// even a string the server failed to escape cannot run or load a remote resource. The plain-text
// part is offered on demand as text. The firm app around the well may say Accrued; this component
// adds no words of its own inside the well.

import { Button, cn } from "@abacus/ui";
import { type JSX, useState } from "react";

export type PreviewWidth = "600" | "390" | "phone";

const CSP =
  "default-src 'none'; style-src 'unsafe-inline'; img-src 'none'; font-src 'none'; " +
  "form-action 'none'; base-uri 'none'";

/** The server's HTML with the policy first in `<head>` (or before everything when it has none). */
export function guardedDocument(html: string): string {
  const meta = `<meta http-equiv="Content-Security-Policy" content="${CSP}">`;
  const at = html.search(/<head[^>]*>/i);
  if (at === -1) return `${meta}${html}`;
  const end = html.indexOf(">", at) + 1;
  return `${html.slice(0, end)}${meta}${html.slice(end)}`;
}

export interface EmailPreviewProps {
  html: string;
  text: string;
  width: PreviewWidth;
  /** The accessible name of the frame ("Email preview"). */
  title: string;
  /** "Show plain text" / "Hide plain text". */
  showText: string;
  hideText: string;
  className?: string;
}

const FRAME: Record<PreviewWidth, string> = {
  "600": "w-full max-w-[600px] h-[640px]",
  "390": "w-[390px] h-[720px]",
  phone: "w-[390px] h-[760px]",
};

export function EmailPreview({
  html,
  text,
  width,
  title,
  showText,
  hideText,
  className,
}: EmailPreviewProps): JSX.Element {
  const [plain, setPlain] = useState(false);
  return (
    <div className={cn("flex flex-col items-center gap-3", className)} data-width={width}>
      <iframe
        title={title}
        sandbox=""
        referrerPolicy="no-referrer"
        srcDoc={guardedDocument(html)}
        className={cn("rounded-pane bg-card shadow-e1", FRAME[width])}
      />
      <Button
        variant="ghost"
        size="sm"
        onClick={() => {
          setPlain((v) => !v);
        }}
        aria-expanded={plain}
      >
        {plain ? hideText : showText}
      </Button>
      {plain ? (
        <pre
          className="w-full max-w-[600px] whitespace-pre-wrap rounded-pane bg-card p-4 text-body text-ink-2 shadow-e1"
          data-testid="email-plain-text"
        >
          {text}
        </pre>
      ) : null}
    </div>
  );
}

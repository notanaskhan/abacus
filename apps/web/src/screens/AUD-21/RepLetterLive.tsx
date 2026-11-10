// AUD-21 on the server's letter (A-07-T28 remainder; DEC-3144), behind `audits.letters`: the
// representations as the structure (general locked, specific with their include state, read-only
// here), the composed paragraphs as the paper and the letter's signers. No artboard words: the
// labels are the screen's, the content is A-07-T24's version. Its own module so a production chunk
// never carries the E0 paper (SPEC-048 AC-10).
import type { RepresentationLetterOut } from "@abacus/api-client";
import { Button, Icon, RegistryStatus } from "@abacus/ui";
import type { JSX } from "react";

export interface RepLetterLiveProps {
  letter: RepresentationLetterOut;
  onBack?: () => void;
}

export function RepLetterLive({ letter, onBack }: RepLetterLiveProps): JSX.Element {
  const general = letter.representations.filter((r) => r.kind === "general");
  const specific = letter.representations.filter((r) => r.kind === "specific");
  return (
    <div data-screen="AUD-21" data-live="true" className="flex min-h-0 flex-1 flex-col">
      <div className="flex h-[50px] items-center gap-2 px-[12px]">
        <Button size="sm" variant="ghost" onClick={onBack}>
          ‹ Cockpit
        </Button>
        <span className="flex-1" />
        <RegistryStatus object="representation_letter" code={letter.status} withDisc={false} />
      </div>
      <div className="flex min-h-0 flex-1 gap-[10px] px-[12px] pb-[12px]">
        <section
          aria-label="Structure"
          className="w-[470px] shrink-0 overflow-y-auto rounded-pane bg-card shadow-e1"
        >
          <h3 className="flex h-[31px] items-center gap-2 bg-band-hd px-[12px] text-dense font-medium">
            General representations (AU-C 580)
            <Icon name="lock" size={12} />
          </h3>
          <ul>
            {general.map((r) => (
              <li key={r.key} className="flex h-[34px] items-center px-[12px] text-[12.5px]">
                {r.title}
              </li>
            ))}
          </ul>
          <h3 className="flex h-[31px] items-center bg-band-hd px-[12px] text-dense font-medium">
            Specific representations
          </h3>
          <ul>
            {specific.map((r) => (
              <li
                key={r.key}
                data-specific={r.key}
                data-included={r.included ? "true" : "false"}
                className="flex min-h-[34px] items-center gap-2 px-[12px] text-[12.5px]"
              >
                <Icon name={r.included ? "circle-check" : "circle"} size={14} />
                <span className="flex-1">{r.title}</span>
              </li>
            ))}
          </ul>
        </section>
        <section
          aria-label="Paper"
          className="min-w-0 flex-1 overflow-y-auto rounded-pane bg-shell p-[14px]"
        >
          <article className="relative mx-auto w-[600px] overflow-hidden rounded-pane bg-card px-[24px] pb-[24px] pt-[20px] text-[12px] leading-[1.55] shadow-e2">
            {letter.watermark === "draft" && (
              <span
                aria-hidden="true"
                data-watermark="draft"
                className="pointer-events-none absolute inset-0 flex -rotate-[30deg] items-center justify-center text-[72px] font-medium text-ink/[.06]"
              >
                DRAFT
              </span>
            )}
            <ol className="list-decimal pl-[18px]">
              {letter.paragraphs.map((p) => (
                <li key={p.key} value={p.number ?? undefined} data-paragraph={p.key}>
                  {p.text}
                </li>
              ))}
            </ol>
            <div className="pt-[18px]">
              {letter.signers.map((s) => (
                <div key={s.contact_id} className="pb-[8px]">
                  <hr className="w-[200px] border-ink-4" />
                  <p className="text-[12px] font-medium">{s.name}</p>
                </div>
              ))}
            </div>
          </article>
        </section>
      </div>
    </div>
  );
}

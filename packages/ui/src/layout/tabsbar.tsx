import type { JSX } from "react";
import { cn } from "../cn";
import { Segmented, type Opt, ViewToggle, type ViewToggleProps } from "../components/tabs";

// The Tabsbar (C-00 Shell Kit spec 05; F-05-T18): the row under the record header that holds the
// shell's only tab style, the C-05 Segmented, centred, with the ViewToggle pinned at the right.
// No fill, no border. 50 for record tabs, 44 (small segmented) for sub-views, 60 for the
// Workbench, which the design pulls up 10px under the toolbar.

export type TabsbarSize = "default" | "compact" | "workbench";

const HEIGHT: Record<TabsbarSize, string> = {
  default: "h-(--tabs-h)",
  compact: "h-(--tabs-h-compact)",
  workbench: "h-(--tabs-h-workbench) -mt-[10px]",
};

export interface TabsbarProps {
  size?: TabsbarSize;
  options: readonly Opt[];
  active?: string;
  /** The tablist's accessible name. */
  label: string;
  onChange?: (label: string) => void;
  /** The grid / list toggle at the right (a ViewToggle's props). Omit for none. */
  view?: Pick<ViewToggleProps, "view" | "views" | "onView" | "forceState">;
  className?: string;
}

export function Tabsbar({
  size = "default",
  options,
  active,
  label,
  onChange,
  view,
  className,
}: TabsbarProps): JSX.Element {
  return (
    <div
      data-shell="tabsbar"
      data-size={size}
      className={cn(
        "relative flex flex-none items-center justify-center",
        HEIGHT[size],
        className,
      )}
    >
      <Segmented
        options={options}
        label={label}
        size={size === "compact" ? "small" : "default"}
        {...(active === undefined ? {} : { active })}
        {...(onChange === undefined ? {} : { onChange })}
      />
      {view !== undefined && (
        <div className="absolute top-[calc(50%-14.5px)] right-(--edge-app) z-20">
          <ViewToggle {...view} />
        </div>
      )}
    </div>
  );
}

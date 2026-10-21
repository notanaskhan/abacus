// What jsdom lacks and Radix's anchored layers (menu, tooltip, popover) read: a ResizeObserver, a
// few pointer-capture methods and scrollIntoView. A test that opens one of them calls
// `installDomShims()` once; nothing here is part of the package's public surface.

class NoopResizeObserver {
  observe(): void {
    // jsdom has no layout, so there is nothing to observe.
  }
  unobserve(): void {
    // See observe.
  }
  disconnect(): void {
    // See observe.
  }
}

export function installDomShims(): void {
  const g = globalThis as { ResizeObserver?: unknown };
  g.ResizeObserver ??= NoopResizeObserver;
  const proto = Element.prototype as unknown as {
    hasPointerCapture?: () => boolean;
    setPointerCapture?: () => void;
    releasePointerCapture?: () => void;
    scrollIntoView?: () => void;
  };
  proto.hasPointerCapture ??= () => false;
  proto.setPointerCapture ??= () => undefined;
  proto.releasePointerCapture ??= () => undefined;
  proto.scrollIntoView ??= () => undefined;
}

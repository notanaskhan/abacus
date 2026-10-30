#!/usr/bin/env bash
# The renderer's byte-stability check (P-11-T02; ADR-320 §3; SPEC-520 AC-30): build the backend
# image's test target, render the golden letter in two fresh containers with no network, compare
# the hashes with each other and with the recorded goldens, then run the image-bound suite.
# `make golden-render` runs this; CI runs it in the render-golden job.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
backend="$(cd "$here/../.." && pwd)"
image="abacus-render-golden:local"

docker build --quiet --target test -t "$image" "$backend" >/dev/null
run() { docker run --rm --network none "$image" python tests/golden_render/render_letter.py; }
a="$(run)"
b="$(run)"
echo "container a: $a"
echo "container b: $b"
if [ "$a" != "$b" ]; then
  echo "FAIL: the two containers rendered different bytes" >&2
  exit 1
fi
pdf="$(echo "$a" | awk '/^pdf/{print $2}')"
docx="$(echo "$a" | awk '/^docx/{print $2}')"
if [ "${RECORD_GOLDEN:-0}" = "1" ]; then
  echo "$pdf  letter.pdf" > "$here/letter.pdf.sha256"
  echo "$docx  letter.docx" > "$here/letter.docx.sha256"
  echo "recorded the goldens"
fi
for kind in pdf docx; do
  want="$(awk '{print $1}' "$here/letter.$kind.sha256" 2>/dev/null || true)"
  got="$([ "$kind" = pdf ] && echo "$pdf" || echo "$docx")"
  if [ "$want" != "$got" ]; then
    echo "FAIL: $kind $got differs from the recorded golden ${want:-<none>}" >&2
    exit 1
  fi
done
# The goldens as committed (or just recorded) are mounted over the image's copy.
docker run --rm --network none -v "$here:/app/tests/golden_render:ro" "$image" \
  pytest tests/golden_render -q -p no:cacheprovider

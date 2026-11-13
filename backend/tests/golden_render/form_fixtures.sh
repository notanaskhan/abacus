#!/usr/bin/env bash
# F-07-T15 (DEC-4731): TPL-17's form-page fixtures, rendered in two fresh containers of the backend
# image with no network, compared byte for byte, then written to the specimen's fixture folder
# (`--check` instead with CHECK=1). `make form-fixtures` runs this.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
backend="$(cd "$here/../.." && pwd)"
out="$(cd "$backend/.." && pwd)/packages/ui/src/specimens/fixtures/tpl-17"
image="abacus-render-golden:local"
mkdir -p "$out"
docker build --quiet --target test -t "$image" "$backend" >/dev/null
run() {
  docker run --rm --network none "$image" \
    python -m abacus_tools.specimens.render_form_fixtures --out /tmp/faces
}
a="$(run)"
b="$(run)"
if [ "$a" != "$b" ]; then
  echo "FAIL: the two containers rendered different form-fixture bytes" >&2
  exit 1
fi
flag=""
if [ "${CHECK:-0}" = "1" ]; then flag="--check"; fi
docker run --rm --network none -v "$out:/out" "$image" \
  python -m abacus_tools.specimens.render_form_fixtures --out /out $flag
echo "form fixtures: $out"

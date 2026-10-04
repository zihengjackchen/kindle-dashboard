#!/bin/sh
# Run on ordinary Linux; pytest also discovers these tests from repository root.
set -eu
cd "$(dirname "$0")/.."
for file in kindle-client/extensions/dashboard/*.sh kindle-client/extensions/dashboard/lib/*.sh; do
    sh -n "$file"
done
if command -v shellcheck >/dev/null 2>&1; then
    shellcheck -x -P SCRIPTDIR kindle-client/extensions/dashboard/*.sh kindle-client/extensions/dashboard/lib/*.sh
fi
python -m pytest scripts/tests -q

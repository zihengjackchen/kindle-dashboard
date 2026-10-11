#!/bin/sh
# NAS-only one-shot job. Reuse the existing authenticated Codex image, without
# mounting research data or giving the dashboard container access to credentials.
set -eu
REPO=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
USAGE_IMAGE=${USAGE_IMAGE:-kindle-dashboard-codex:0.162.1}
USAGE_AUTH_DIR=${USAGE_AUTH_DIR:-/mnt/Main/tgp/secrets/codex}
USAGE_UID=${USAGE_UID:-568}
USAGE_GID=${USAGE_GID:-568}
USAGE_READER_GID=${USAGE_READER_GID:-10001}
USAGE_OUTPUT_DIR=${USAGE_OUTPUT_DIR:-$REPO/server/data/codex}
[ -d "$USAGE_AUTH_DIR" ] && [ -d "$USAGE_OUTPUT_DIR" ] || {
    printf 'Usage auth/output directory missing; see docs/codex-usage.md\n' >&2; exit 1;
}
# A host lock prevents overlapping cron/manual runs. It never locks Codex itself.
exec 9> "$USAGE_OUTPUT_DIR/.refresh.lock"
flock -n 9 || exit 0
cid_dir=$(mktemp -d /tmp/dashboard-usage.XXXXXX)
cleanup_usage() {
    if [ -s "$cid_dir/id" ]; then
        usage_cid=$(cat "$cid_dir/id")
        case "$usage_cid" in ''|*[!a-f0-9]*) ;; *) docker rm -f "$usage_cid" >/dev/null 2>&1 || : ;; esac
    fi
    rm -f "$cid_dir/id"
    rmdir "$cid_dir" 2>/dev/null || :
}
trap cleanup_usage 0
trap 'exit 130' INT
trap 'exit 143' TERM HUP
timeout 90 docker run --rm --init --cidfile "$cid_dir/id" \
    --read-only --cap-drop ALL --security-opt no-new-privileges:true \
    --user "$USAGE_UID:$USAGE_GID" --group-add "$USAGE_READER_GID" \
    --memory 256m --pids-limit 64 --log-driver none \
    --tmpfs "/tmp:rw,size=32m,mode=1777" \
    --tmpfs "/data:rw,size=8m,uid=$USAGE_UID,gid=$USAGE_GID,mode=700" \
    --mount "type=bind,source=$USAGE_AUTH_DIR,target=/codex" \
    --mount "type=bind,source=$REPO/scripts/export-codex-usage.py,target=/usage-export.py,readonly" \
    --mount "type=bind,source=$USAGE_OUTPUT_DIR,target=/output" \
    --workdir /tmp --entrypoint python "$USAGE_IMAGE" \
    /usage-export.py --codex /usr/local/bin/codex --output /output/usage.json

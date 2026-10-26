#!/bin/sh
# witness observer hook — PostToolUse (post_tool_use)
#
# Content-free by construction (RULE-1 analog, see docs/LIMITATIONS.md and
# docs/ARCHITECTURE.md): this script NEVER writes the bytes it receives
# (stdin, argv, env) to its output log. It only records a sha256 digest of
# whatever stdin it was handed, a byte count, an argv count, and a
# timestamp. The real invocation shape (stdin vs. env vs. argv for the
# payload Muse Code hands a hook) is unverified in this build — see
# docs/LIMITATIONS.md — so this script defensively digests whatever it
# finds on stdin rather than assuming a specific contract, and bounds the
# read to 0.5s (well inside the manifest's 1000ms hook timeout) so an
# open-but-silent stdin can never hang the hook. It never prints anything
# to stdout and always exits 0, so it can never be mistaken for a
# blocking decision on a real tool call.
#
# Implementation note: the stdin-drain is backgrounded so it can be
# time-bounded, but POSIX shells redirect a backgrounded job's stdin from
# /dev/null unless an explicit redirection is present — `exec 3<&0` saves
# the real stdin to fd 3 first so `cat <&3` reads the genuine input
# (empirically confirmed; a naive `cat > "$TMP" &` silently captured 0
# bytes in this build's own manual test).
#
# Output: one JSON line appended to $WITNESS_HOOK_LOG (default:
# /tmp/witness_muse_hook_events.jsonl), tailable by witness's own
# `Tailer` (see src/witness/muse_journal.py).

EVENT_NAME="PostToolUse"
HOOK_ID="post_tool_use"
OUT="${WITNESS_HOOK_LOG:-/tmp/witness_muse_hook_events.jsonl}"

STDIN_BYTES=0
STDIN_DIGEST="null"

exec 3<&0
TMP=$(mktemp "${TMPDIR:-/tmp}/witness_hook_stdin.XXXXXX" 2>/dev/null || echo "/tmp/witness_hook_stdin.$$")
cat <&3 > "$TMP" 2>/dev/null &
CATPID=$!
i=0
while [ $i -lt 10 ]; do
    kill -0 "$CATPID" 2>/dev/null || break
    sleep 0.05
    i=$((i + 1))
done
kill "$CATPID" 2>/dev/null
wait "$CATPID" 2>/dev/null

if [ -s "$TMP" ]; then
    STDIN_BYTES=$(wc -c < "$TMP" | tr -d ' ')
    if command -v shasum >/dev/null 2>&1; then
        DIGEST=$(shasum -a 256 "$TMP" | awk '{print $1}')
    elif command -v sha256sum >/dev/null 2>&1; then
        DIGEST=$(sha256sum "$TMP" | awk '{print $1}')
    else
        DIGEST=""
    fi
    if [ -n "$DIGEST" ]; then
        STDIN_DIGEST="\"sha256:${DIGEST}\""
    fi
fi
rm -f "$TMP"

ARGV_COUNT=$#
TS=$(date +%s)

printf '{"event":"%s","hook_id":"%s","ts":%s,"stdin_bytes":%s,"stdin_sha256":%s,"argv_count":%s}\n' \
    "$EVENT_NAME" "$HOOK_ID" "$TS" "$STDIN_BYTES" "$STDIN_DIGEST" "$ARGV_COUNT" >> "$OUT" 2>/dev/null

exit 0

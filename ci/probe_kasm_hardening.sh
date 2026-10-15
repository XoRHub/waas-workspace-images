#!/bin/sh
# probe_kasm_hardening.sh — empirically determine whether an upstream
# kasmweb/* image (not built by us: no HARDENING.md doctrine to derive a
# profile from statically) tolerates a hardened pod securityContext, the
# way waas-core-images' smoke test proves it for our own images: run the
# container under those constraints and see if it survives, rather than
# trust what the upstream Dockerfile merely declares.
#
#   0. `docker pull` up front: `docker run` would pull implicitly but
#      silently, and for a multi-GB desktop image that looks like a hang.
#      Failure (bad ref, network down) -> "unknown".
#   1. Plain `docker run` — confirms the documented Kasm baseline
#      (non-root UID 1000). Never up, or not UID 1000 -> "unknown": no
#      claim about anything stronger is safe.
#   2. A second run of the same ref with --read-only --cap-drop ALL
#      --security-opt no-new-privileges (kasm images use /home/kasm-user,
#      verified against kasmtech/workspaces-images). Still running after
#      the wait -> "hardened"; exited/crash-looped -> "normal".
#
# Prints exactly one of hardened | normal | unknown to stdout and nothing
# else (everything else goes to stderr: generate_kasm_catalog.py parses
# stdout verbatim). Always exits 0 — the verdict IS the output, so one
# flaky image can never fail the catalog job.
set -u

IMAGE="${1:?usage: probe_kasm_hardening.sh <image-ref>}"
NAME="probe-$$"

cleanup() {
    docker rm -f "${NAME}" >/dev/null 2>&1 || true
}

wait_running() {
    # ~30s for the container to reach Running; one that never starts is
    # as inconclusive as one that exits at once under hardening.
    i=0
    while [ $i -lt 15 ]; do
        [ "$(docker inspect -f '{{.State.Running}}' "${NAME}" 2>/dev/null)" = "true" ] && return 0
        i=$((i + 1)); sleep 2
    done
    return 1
}

echo "pulling ${IMAGE} ..." >&2
if ! docker pull "${IMAGE}" >&2; then
    echo unknown
    exit 0
fi

if ! docker run -d --name "${NAME}" "${IMAGE}" >/dev/null 2>&1; then
    echo unknown
    exit 0
fi

if ! wait_running; then
    cleanup
    echo unknown
    exit 0
fi

UID_SEEN=$(docker exec "${NAME}" id -u 2>/dev/null || true)
cleanup

if [ "${UID_SEEN}" != "1000" ]; then
    echo unknown
    exit 0
fi

if ! docker run -d --name "${NAME}" \
    --read-only --cap-drop ALL --security-opt no-new-privileges \
    --tmpfs /tmp --tmpfs /run --tmpfs /home/kasm-user:mode=1777 \
    "${IMAGE}" >/dev/null 2>&1; then
    echo normal
    exit 0
fi

# Surviving the same ~30s a working container needs to initialize, plus
# a beat, is the proxy for "tolerates the hardened profile".
if wait_running && sleep 15 && [ "$(docker inspect -f '{{.State.Running}}' "${NAME}" 2>/dev/null)" = "true" ]; then
    cleanup
    echo hardened
else
    cleanup
    echo normal
fi

# infra/opa/Dockerfile
#
# Fallback derived image — see 01-03-SUMMARY.md "OPA Pre-Flight Result" for
# why this exists. RESEARCH.md's Assumption A1 (the `-debug` tag's busybox
# ships a working `wget` applet) was runtime-verified FALSE at
# implementation time: `docker run --rm --entrypoint sh
# openpolicyagent/opa:1.19.1-debug -c "busybox --list"` lists no wget, curl,
# or nc applet at all, and the image has no package manager (no apk binary,
# despite /etc/apk metadata being present) to install one at build time.
#
# Fix: multi-stage COPY of a Chainguard-published, Wolfi-based curl image.
# `cgr.dev/chainguard/curl` is built from the same Wolfi distribution as
# `openpolicyagent/opa`, so its curl binary and shared libraries are ABI
# compatible with this base — copying its entire minimal rootfs over the
# OPA image adds a working `curl` without touching OPA's own binary,
# ENTRYPOINT (`/opa`), or runtime user (`1000:1000`), all of which are
# verified unchanged after the copy (`docker image inspect` diff, this
# session).
#
# Pinned by digest, not `:latest` — Chainguard's free-tier registry only
# publishes a rolling `latest` tag for this image (no versioned tags
# without a paid subscription), so a digest pin is the only way to satisfy
# D-04's exact-reproducibility intent for this build-time-only stage.
FROM cgr.dev/chainguard/curl@sha256:8cb68f34d752c6d0136bf9f64ae8a03e0eafc0933e53271307d3ee0889b979bc AS curltool

FROM openpolicyagent/opa:1.19.1-debug
COPY --from=curltool / /

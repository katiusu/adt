#!/usr/bin/env bash
#
# Tests for the release-download integrity helpers in setup.sh:
#   verify_asset_digest   — SHA256 of a downloaded archive vs the release digest
#   verify_payload_arch   — refuse an x86_64 payload before it reaches $SDK_ROOT
#
# Both exist because of a real failure on an ARM64 host: the installer fetched a
# Google linux-x86_64 tarball, reported success, and the binaries only failed at
# exec time ("bad machine"). These helpers must reject such a payload *before*
# anything is written into the SDK.
#
# Run: ./tests/test_release_integrity.sh

set -uo pipefail

SCRIPT_DIR="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SETUP_SH="${SCRIPT_DIR}/../setup.sh"
WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

pass=0
fail=0

assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    if [[ "$actual" == "$expected" ]]; then
        echo "ok - $desc"
        pass=$((pass + 1))
    else
        echo "NOT OK - $desc (expected '$expected', got '$actual')"
        fail=$((fail + 1))
    fi
}

assert_not_contains() {
    local desc="$1" needle="$2" haystack="$3"
    if [[ "$haystack" != *"$needle"* ]]; then
        echo "ok - $desc"
        pass=$((pass + 1))
    else
        echo "NOT OK - $desc (must not contain '$needle', got: ${haystack//$'\n'/ | })"
        fail=$((fail + 1))
    fi
}

assert_contains() {
    local desc="$1" needle="$2" haystack="$3"
    if [[ "$haystack" == *"$needle"* ]]; then
        echo "ok - $desc"
        pass=$((pass + 1))
    else
        echo "NOT OK - $desc (expected to contain '$needle', got: ${haystack//$'\n'/ | })"
        fail=$((fail + 1))
    fi
}

# Source setup.sh without running main, then call one of its functions.
# SDK_ROOT is set *after* sourcing: setup.sh initialises it itself, so an
# environment value alone would be overwritten.
call_setup() {
    ADT_SOURCE_ONLY=1 bash -c 'source "$1"; shift; SDK_ROOT="$1"; shift; "$@"' \
        _ "$SETUP_SH" "$WORKDIR/sdk" "$@"
}

# Fixtures: a real ARM64 ELF from this host, a text shim, and a fake x86_64 ELF.
make_arm64() { mkdir -p "$(dirname "$1")"; cp /bin/true "$1"; chmod +x "$1"; }
make_script() { mkdir -p "$(dirname "$1")"; printf '#!/bin/sh\nexit 0\n' > "$1"; chmod +x "$1"; }
make_x86_64() {
    mkdir -p "$(dirname "$1")"
    python3 - "$1" <<'PY'
import struct, sys
ident = b"\x7fELF" + bytes([2, 1, 1, 0]) + b"\x00" * 8
header = struct.pack("<HHI", 2, 62, 1)   # ET_EXEC, EM_X86_64, EV_CURRENT
with open(sys.argv[1], "wb") as handle:
    handle.write(ident + header + b"\x00" * 64)
PY
    chmod +x "$1"
}

assert_eq "fixture: /bin/true is a native ARM64 ELF here" "arm64" "$(call_setup detect_binary_arch /bin/true)"

echo ""
echo "== verify_payload_arch =="

# 1. A pure-ARM64 payload is accepted and reports what it checked.
p="$WORKDIR/ok"
make_arm64 "$p/build-tools/aapt2"; make_arm64 "$p/build-tools/aapt"; make_arm64 "$p/build-tools/zipalign"
out="$(call_setup verify_payload_arch "$p" build-tools 2>&1)"; rc=$?
assert_eq "arm64 payload accepted (exit)" "0" "$rc"
assert_contains "arm64 payload reports the count" "3 ARM64-compatible" "$out"

# 2. One x86_64 binary is enough to refuse the whole payload.
p="$WORKDIR/bad"
make_arm64 "$p/build-tools/aapt2"; make_x86_64 "$p/build-tools/aapt"
out="$(call_setup verify_payload_arch "$p" build-tools 2>&1)"; rc=$?
assert_eq "x86_64 payload refused (exit)" "1" "$rc"
assert_contains "x86_64 payload names the offending binary" "aapt" "$out"
assert_contains "x86_64 payload explains what is wrong" "x86_64" "$out"
assert_contains "x86_64 payload promises the SDK is untouched" "left untouched" "$out"

# 3. Mixed payload (arm64 + x86_64) is refused too.
p="$WORKDIR/mixed"
make_arm64 "$p/build-tools/aapt2"; make_x86_64 "$p/build-tools/zipalign"
out="$(call_setup verify_payload_arch "$p" build-tools 2>&1)"; rc=$?
assert_eq "mixed payload refused (exit)" "1" "$rc"

# 4. Text shims delegate, so they are acceptable.
p="$WORKDIR/shim"
make_script "$p/build-tools/aapt2"
out="$(call_setup verify_payload_arch "$p" build-tools 2>&1)"; rc=$?
assert_eq "text shim accepted (exit)" "0" "$rc"

# 5. payloads unpacked under a different subdirectory still get checked.
p="$WORKDIR/nested"
make_x86_64 "$p/android-sdk/platform-tools/adb"
out="$(call_setup verify_payload_arch "$p" platform-tools 2>&1)"; rc=$?
assert_eq "x86_64 payload in a nested dir refused (exit)" "1" "$rc"
assert_contains "nested payload names adb" "adb" "$out"

# 6. platform-tools payloads hit the same check.
p="$WORKDIR/pt"
make_arm64 "$p/platform-tools/adb"; make_x86_64 "$p/platform-tools/fastboot"
out="$(call_setup verify_payload_arch "$p" platform-tools 2>&1)"; rc=$?
assert_eq "platform-tools x86_64 refused (exit)" "1" "$rc"
assert_contains "platform-tools names fastboot" "fastboot" "$out"

echo ""
echo "== verify_asset_digest =="

archive="$WORKDIR/payload.tar.gz"
printf 'not really a tarball, just bytes for hashing\n' > "$archive"
good="sha256:$(sha256sum "$archive" | awk '{print $1}')"

out="$(call_setup verify_asset_digest "$archive" "$good" 2>&1)"; rc=$?
assert_eq "matching digest accepted (exit)" "0" "$rc"
assert_contains "matching digest confirms verification" "SHA256 verified" "$out"

out="$(call_setup verify_asset_digest "$archive" "sha256:$(printf '0%.0s' $(seq 1 64))" 2>&1)"; rc=$?
assert_eq "mismatched digest refused (exit)" "1" "$rc"
assert_contains "mismatched digest reports the mismatch" "SHA256 mismatch" "$out"

out="$(call_setup verify_asset_digest "$archive" "" 2>&1)"; rc=$?
assert_eq "missing digest warns but installs (exit)" "0" "$rc"
assert_contains "missing digest is announced" "installing unverified" "$out"

echo ""
echo "== run_sdkmanager ARM64 guard =="

# A stub sdkmanager proves the guard refuses before anything is launched.
mkdir -p "$WORKDIR/sdk/cmdline-tools/latest/bin"
printf '#!/bin/sh\necho "SDKMANAGER CALLED: $*"\n' > "$WORKDIR/sdk/cmdline-tools/latest/bin/sdkmanager"
chmod +x "$WORKDIR/sdk/cmdline-tools/latest/bin/sdkmanager"

out="$(call_setup run_sdkmanager 'platforms;android-35' 2>&1)"; rc=$?
assert_eq "arch-neutral platform passes through (exit)" "0" "$rc"
assert_contains "sdkmanager was actually invoked" "SDKMANAGER CALLED" "$out"
assert_contains "platform argument reached sdkmanager" "platforms;android-35" "$out"

out="$(call_setup run_sdkmanager --licenses 2>&1)"; rc=$?
assert_eq "--licenses passes through (exit)" "0" "$rc"

out="$(call_setup run_sdkmanager 'build-tools;35.0.0' 2>&1)"; rc=$?
assert_eq "sdkmanager build-tools refused (exit)" "1" "$rc"
assert_contains "refusal names install-build-tools" "install-build-tools" "$out"
assert_not_contains "refused build-tools never reaches sdkmanager" "SDKMANAGER CALLED" "$out"

out="$(call_setup run_sdkmanager platform-tools 2>&1)"; rc=$?
assert_eq "sdkmanager platform-tools refused (exit)" "1" "$rc"
assert_contains "refusal names install-platform-tools" "install-platform-tools" "$out"

out="$(call_setup run_sdkmanager 'ndk;27.2.12479018' 2>&1)"; rc=$?
assert_eq "NDK package still allowed through (exit)" "0" "$rc"

echo ""
echo "== ${pass} passed, ${fail} failed =="
[[ $fail -eq 0 ]]

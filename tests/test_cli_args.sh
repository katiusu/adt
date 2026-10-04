#!/usr/bin/env bash
#
# Tests for the CLI-argument handling in setup.sh:
#   take_sdk_root_arg — doctor/status/cleanup honour --sdk-root
#   configure_gradle  — never clobbers a shim that lives outside $SDK_ROOT
#
# Both come from a real ARM64 session: `doctor --sdk-root <path>` silently
# reported on an empty ~/android-sdk instead of the SDK it was pointed at, and
# `setup-gradle` replaced a deliberate local aapt2 wrapper (then printed a
# success message) whose argument rewriting AGP needed on this host.
#
# Run: ./tests/test_cli_args.sh

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

# Same, but with an isolated $HOME so configure_gradle cannot touch the real one.
call_setup_home() {
    local home="$1"; shift
    HOME="$home" ADT_SOURCE_ONLY=1 bash -c 'source "$1"; shift; SDK_ROOT="$1"; shift; "$@"' \
        _ "$SETUP_SH" "$WORKDIR/sdk" "$@"
}

echo "== take_sdk_root_arg =="

out="$(ADT_SOURCE_ONLY=1 bash -c 'source "$1"; SDK_ROOT=""; take_sdk_root_arg --sdk-root /tmp/some-sdk; echo "SDK_ROOT=${SDK_ROOT}"' _ "$SETUP_SH" 2>&1)"
assert_contains "take_sdk_root_arg sets SDK_ROOT" "SDK_ROOT=/tmp/some-sdk" "$out"

out="$(ADT_SOURCE_ONLY=1 bash -c 'source "$1"; SDK_ROOT=""; take_sdk_root_arg --sdk-root; echo "SDK_ROOT=${SDK_ROOT}"' _ "$SETUP_SH" 2>&1)"; rc=$?
assert_eq "bare --sdk-root is rejected (exit)" "1" "$rc"
assert_contains "bare --sdk-root explains itself" "--sdk-root requires a path" "$out"

out="$(ADT_SOURCE_ONLY=1 bash -c 'source "$1"; SDK_ROOT=/keep; take_sdk_root_arg -v; echo "SDK_ROOT=${SDK_ROOT}"' _ "$SETUP_SH" 2>&1)"; rc=$?
assert_eq "unrelated arguments are ignored (exit)" "0" "$rc"
assert_contains "unrelated arguments leave SDK_ROOT alone" "SDK_ROOT=/keep" "$out"

echo ""
echo "== read-only commands honour --sdk-root =="

mkdir -p "$WORKDIR/sdkroot/build-tools/37.0.0"
cp /bin/true "$WORKDIR/sdkroot/build-tools/37.0.0/aapt2"

out="$(call_setup cmd_status --sdk-root "$WORKDIR/sdkroot" 2>&1)"
assert_contains "status reports the requested root" "$WORKDIR/sdkroot" "$out"
assert_not_contains "status does not fall back to ~/android-sdk" "$HOME/android-sdk" "$out"

out="$(call_setup cmd_doctor --sdk-root "$WORKDIR/sdkroot" 2>&1)"
assert_contains "doctor reports the requested root" "$WORKDIR/sdkroot" "$out"
assert_not_contains "doctor does not fall back to ~/android-sdk" "$HOME/android-sdk" "$out"

echo ""
echo "== configure_gradle keeps a foreign override =="

home="$WORKDIR/home"
mkdir -p "$home/.gradle"
props="$home/.gradle/gradle.properties"
sdk="$WORKDIR/sdk"
mkdir -p "$sdk/build-tools/37.0.0"
cp /bin/true "$sdk/build-tools/37.0.0/aapt2"
new_aapt2="$sdk/build-tools/37.0.0/aapt2"

printf '# my settings\nandroid.aapt2FromMavenOverride=/opt/my-shim/aapt2\n' > "$props"

out="$(call_setup_home "$home" configure_gradle "$new_aapt2" 2>&1)"; rc=$?
assert_eq "keeping a foreign override succeeds (exit)" "0" "$rc"
assert_contains "it reports that the override was kept" "Kept the existing aapt2 override: /opt/my-shim/aapt2" "$out"
assert_contains "it says how to force a rewrite" "setup-gradle --force" "$out"
assert_eq "the file still points at the foreign shim" "android.aapt2FromMavenOverride=/opt/my-shim/aapt2" "$(grep '^android\.aapt2FromMavenOverride=' "$props")"
assert_eq "unrelated lines survived" "# my settings" "$(head -n 1 "$props")"
assert_eq "a timestamped backup was written" "1" "$(find "$home/.gradle" -maxdepth 1 -name 'gradle.properties.bak-*' | wc -l | tr -d ' ')"

out="$(call_setup_home "$home" configure_gradle "$new_aapt2" --force 2>&1)"; rc=$?
assert_eq "--force rewrites the override (exit)" "0" "$rc"
assert_eq "--force points the file at the requested aapt2" "android.aapt2FromMavenOverride=$new_aapt2" "$(grep '^android\.aapt2FromMavenOverride=' "$props")"

# An override that already lives inside the SDK is ours: rewrite it silently.
printf 'android.aapt2FromMavenOverride=%s\n' "$sdk/build-tools/36.0.0/aapt2" > "$props"
out="$(call_setup_home "$home" configure_gradle "$new_aapt2" 2>&1)"; rc=$?
assert_eq "an in-SDK override is replaced (exit)" "0" "$rc"
assert_eq "in-SDK override now points at the new build-tools" "android.aapt2FromMavenOverride=$new_aapt2" "$(grep '^android\.aapt2FromMavenOverride=' "$props")"
assert_not_contains "an in-SDK override is not reported as kept" "Kept the existing aapt2 override" "$out"

echo ""
echo "== ${pass} passed, ${fail} failed =="
[[ $fail -eq 0 ]]

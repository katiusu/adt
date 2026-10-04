# AI_ASSISTANT.md - Project Knowledge Base

## Project Overview

**ADT** (`soobujmiah/adt`) builds Android SDK tools (aapt2, aapt, aidl, zipalign, adb, fastboot, etc.) as native Linux ARM64 binaries from official AOSP source code.

This project adapts [lzhiyong/android-sdk-tools](https://github.com/lzhiyong/android-sdk-tools) (which targets Android/Bionic via NDK) to target Linux/glibc using the system compiler. The Linux/glibc adaptation lineage, including the version-registry entries verified on Fedora Asahi 43, comes from `hamza72x/android-sdk-linux-arm64`; ADT continues that work with on-device Termux/PRoot ARM64 validation and is self-hosted: `setup.sh` downloads/clones only from `soobujmiah/adt`, and releases (when tagged) are published by `.github/workflows/build.yml` on this repository.

## Agent Operating Rules

**SKB continuity:** this repository follows `SKB_KNOWLEDGE_RETURN.md` for knowledge return. For the cross-project engineering baseline (cloud-first build policy, authorization boundaries, session-close discipline), consult `soobujmiah/skb` → `AGENT_NAVIGATION.md`, `engineering/HEAVY_BUILD_AND_ARTIFACT_WORKFLOW.md`, and `standards/human-authority-gate.md`. This file states only what is specific to ADT; it does not restate the SKB baseline.

**Source of truth, in order:** `versions.json` (per-version verified/unverified/shim status and release fields) → this file and `README.md`/`COMMANDS.md` → live CI (`.github/workflows/ci.yml`, `build.yml`) → `docs/REAL_DEVICE_BUILD_VALIDATION.md` and `docs/ANDROID_ARM64_BUILD_HANDOFF.md` for physical-device evidence. Source code and recent commits are authoritative over any of the above when they disagree.

**Local vs. cloud execution (ADT-specific):** AOSP source cloning and native compilation (`get_source.py`, `build.py`) are heavy and belong on GitHub Actions (`ubuntu-24.04-arm`), which is what `ci.yml`/`build.yml` already do for every verified version on every push/tag — do not re-run a full AOSP build locally merely to confirm it works. This is a **device-health policy choice, not a capability gap**: ADT itself proves Sobuj's Termux/PRoot phone environment can run a real ARM64 native Android toolchain locally, so a local source build is technically possible, it's just avoided by default to keep CPU/thermal/battery/storage load off the phone. Only the *build/compile* step is remote by default. Everything else stays local on the phone: running `setup.sh` (install/doctor/status), installing artifacts (checked-in tarball → GitHub Release → source build, in that order per the registry rule below), ADB/device work, real-device validation (`docs/REAL_DEVICE_BUILD_VALIDATION.md`), reading logs/CI output, debugging a failure, and fixing the source — the local Termux/PRoot setup is Sobuj's actual repo workstation (clone/edit/branch/commit), not just a dispatcher for remote jobs. A local source build itself is appropriate only to diagnose a build/environment failure CI can't reproduce (e.g. a Termux/PRoot-only toolchain quirk), when explicitly asked to validate the local build path, or whenever Sobuj specifically requests a local build — not as the default way to add or verify a version.

**Evidence vocabulary:** a version's `status` in `versions.json` (`verified`/`unverified`/`shim`) is a build-verification claim backed by a green CI run for that version, checked with `file`/ELF-arch verification — it is not a device-execution claim. A `release` field means a GitHub Release actually exists with downloadable assets, not that a release is merely planned. Device-execution or performance claims require `docs/REAL_DEVICE_BUILD_VALIDATION.md`-style evidence, not CI success alone.

**Push-validated-work-first:** once a change is actually validated (tests/CI green, or device-validated where that's the relevant bar), commit and push it before starting further work or a next validation round — don't let validated work sit unpushed on the single phone/PRoot working copy where it can be lost. Push first, then continue.

**Session close:** review `git diff`/`git status`, confirm CI status for any touched version (from the raw run log, not just the checkmark), update `versions.json`/`docs/` when status changed, run the SKB knowledge-return review from `SKB_KNOWLEDGE_RETURN.md`, then commit and push validated work right away — don't leave it staged/unpushed.

## Repository Layout

```
.
├── PLAN.md              # Detailed build plan and architecture
├── AI_ASSISTANT.md      # This file - project knowledge for agents/contributors
├── README.md            # User-facing documentation
├── COMMANDS.md          # Per-tool usage reference (English docs + exact commands); printed-link at end of bootstrap
├── .gitignore           # Ignores src/ (AOSP clones) and build/ (output)
├── .github/workflows/   # CI/CD
│   ├── ci.yml           # Sanity check on push to main (verified versions only)
│   └── build.yml        # Build + Release on tag push (v*)
├── repos.json           # List of AOSP repos to clone (all android.googlesource.com)
├── versions.json        # Version registry: status, AOSP tags, release info
├── get_source.py        # Clones AOSP repos and applies patches (version-aware)
├── build.py             # Build orchestrator (CMake + Ninja, Linux native)
├── CMakeLists.txt       # Root CMake configuration
├── build-tools/         # CMake definitions for build-tools binaries
│   ├── CMakeLists.txt
│   ├── aapt.cmake
│   ├── aapt2.cmake
│   ├── aidl.cmake
│   ├── zipalign.cmake
│   ├── dexdump.cmake
│   └── split-select.cmake
├── lib/                 # CMake definitions for support libraries
│   ├── CMakeLists.txt
│   ├── libbase.cmake
│   ├── liblog.cmake
│   ├── libcutils.cmake
│   ├── libutils.cmake
│   ├── libandroidfw.cmake
│   ├── libziparchive.cmake
│   ├── libincfs.cmake
│   ├── libselinux.cmake
│   ├── libsepol.cmake
│   ├── libbuildversion.cmake
│   ├── libpackagelistparser.cmake
│   ├── libprocessgroup.cmake
│   ├── libsparse.cmake
│   ├── libusb.cmake
│   ├── libdiagnoseusb.cmake
│   ├── libmdnssd.cmake
│   ├── libopenscreen.cmake
│   ├── libabsl.cmake
│   └── libprotoc.cmake
├── platform-tools/      # CMake definitions for platform-tools binaries
│   ├── CMakeLists.txt
│   ├── adb.cmake
│   ├── fastboot.cmake
│   ├── e2fsprogs.cmake
│   ├── f2fs-tools.cmake
│   ├── hprof-conv.cmake
│   ├── sqlite3.cmake
│   └── etc1tool.cmake
├── others/              # Additional tools
│   ├── CMakeLists.txt
│   └── veridex.cmake
├── patches/             # Source patches for AOSP code (versioned)
│   ├── base/            # Universal patches (GCC/glibc compat, all versions)
│   │   ├── misc/        # Pre-generated headers and source files
│   │   │   ├── protobuf_config.h
│   │   │   ├── deployagent.inc
│   │   │   ├── deployagentscript.inc
│   │   │   ├── dex_operator_out.cc
│   │   │   ├── IncrementalProperties.sysprop.cpp
│   │   │   ├── IncrementalProperties.sysprop.h
│   │   │   └── platform_tools_version.h
│   │   ├── libbase.patch
│   │   ├── logging.patch
│   │   ├── core.patch
│   │   ├── base.patch
│   │   ├── incremental_delivery.patch
│   │   ├── openscreen.patch
│   │   ├── adb.patch
│   │   ├── aidl.patch
│   │   ├── build.patch
│   │   └── art.patch
│   ├── build-tools/     # Version-specific overrides for build-tools
│   │   └── 35.0.2/
│   │       └── misc/
│   │           └── platform_tools_version.h
│   └── platform-tools/  # Version-specific overrides for platform-tools
│       └── 35.0.2/
│           └── misc/
│               ├── deployagent.inc
│               ├── deployagentscript.inc
│               └── platform_tools_version.h
├── setup.sh             # End-user installer script
├── src/                 # [gitignored] AOSP source code (~38 repos)
└── build/               # [gitignored] CMake build output
```

## Key Technical Decisions

### 1. Linux Native vs Android NDK

The upstream lzhiyong repo builds for Android (Bionic libc) using the NDK. We target Linux (glibc) with the system compiler. Key differences:

- **No `c++_static`**: NDK's bundled libc++ is replaced by system libstdc++ (linked automatically by GCC)
- **No NDK toolchain file**: We use CMake's default native compilation
- **`-lpthread`**: Explicit pthread linking needed on Linux (Bionic includes it implicitly)
- **No `ANDROID` define**: AOSP code has `#ifdef __ANDROID__` guards; without it, Linux code paths activate

### 2. Source Origin

ALL C/C++ source code comes from `https://android.googlesource.com/platform/...` (official Google AOSP mirrors). The `repos.json` file lists every repository. No third-party source code is used beyond what AOSP itself depends on.

### 3. Protobuf Two-Stage Build

Protobuf requires a two-stage build:
1. Build `protoc` natively for the host (using AOSP's bundled protobuf with system cmake)
2. Use that `protoc` to generate `.pb.cc`/`.pb.h` files during the main build

The host `protoc` path is passed via `-DPROTOC_PATH=...` to CMake.

### 4. libcutils Android-Only Sources

The original build includes Android kernel-specific source files in libcutils. These are excluded for Linux:
- `ashmem-dev.cpp` (Android shared memory)
- `android_reboot.cpp` (Android reboot syscall)
- `trace-dev.cpp` (Android atrace)
- `klog.cpp` (kernel log)
- `qtaguid.cpp` (network tagging)
- `uevent.cpp` (kernel uevents)
- `partition_utils.cpp` (Android partitions)

### 5. liblog FAKE_LOG_DEVICE

liblog is compiled with `-DFAKE_LOG_DEVICE=1` which routes Android logging to stderr instead of the Android logd daemon. This is critical for host builds.

## Build Commands

### Full Build
```bash
# Clone AOSP sources (with version-specific patch resolution)
python3 get_source.py --tags platform-tools-35.0.2 \
    --component build-tools --version 35.0.2

# Build host protoc
cd src/protobuf && mkdir build && cd build
cmake -GNinja -Dprotobuf_BUILD_TESTS=OFF ..
ninja -j$(nproc)
cd ../../..

# Build all tools (versioned build dir)
python3 build.py --protoc=$(pwd)/src/protobuf/build/protoc \
    --build=build/build-tools-35.0.2
```

### Build Single Target
```bash
python3 build.py --protoc=$(pwd)/src/protobuf/build/protoc \
    --build=build/build-tools-35.0.2 --target=aapt2
```

### Clean Build
```bash
rm -rf build/build-tools-35.0.2/
python3 build.py --protoc=$(pwd)/src/protobuf/build/protoc \
    --build=build/build-tools-35.0.2
```

## Dependencies (Build Host)

`setup.sh` source builds (`build-build-tools` / `build-platform-tools` / `build-all`) auto-install the full set below when they detect missing tools and root/sudo is available; otherwise they print the exact root command and stop. After a successful build the script offers to delete the ~2-4 GB `src/` + `build/` trees (kept on answered-no or on failure, for debugging; `./setup.sh cleanup` sweeps them later). The manual dependency commands remain:

### Required Packages

| Package | Purpose |
|---------|---------|
| `gcc`, `g++` | C/C++ compiler |
| `cmake` (>= 3.14) | Build system generator |
| `ninja-build` | Build executor |
| `git` | Clone AOSP repos |
| `python3` | Build scripts |
| `golang` | Required by some AOSP components |
| `bison` | Parser generator (for aidl) |
| `flex` | Lexer generator (for aidl, libsepol) |
| `zlib-devel` | Compression library |
| `openssl-devel` | Crypto (for boringssl fallback headers) |
| `libusb1-devel` | USB device access (for adb) |
| `pcre2-devel` | Regex library (for libselinux) |
| `expat-devel` | XML parsing (for aapt/aapt2) |
| `libpng-devel` | PNG processing (for aapt/aapt2) |

### Fedora/RHEL
```bash
sudo dnf install gcc gcc-c++ cmake ninja-build git python3 golang bison flex \
    zlib-devel openssl-devel libusb1-devel pcre2-devel expat-devel libpng-devel
```

### Ubuntu/Debian
```bash
sudo apt install gcc g++ cmake ninja-build git python3 golang bison flex \
    zlib1g-dev libssl-dev libusb-1.0-0-dev libpcre2-dev libexpat1-dev libpng-dev
```

## Output Binaries

After a successful build, all binaries are in `build/<component>-<version>/bin/` (flat directory):

### build-tools
| Binary | Description |
|--------|-------------|
| `aapt` | Android Asset Packaging Tool (legacy) |
| `aapt2` | Android Asset Packaging Tool 2 (used by Gradle/AGP) |
| `aidl` | Android Interface Definition Language compiler |
| `zipalign` | APK zip alignment tool |
| `dexdump` | DEX file disassembler/inspector |
| `split-select` | APK split selection tool |

### platform-tools
| Binary | Description |
|--------|-------------|
| `adb` | Android Debug Bridge |
| `fastboot` | Device bootloader flashing tool |
| `sqlite3` | SQLite CLI (Android version) |
| `etc1tool` | ETC1 texture tool |
| `hprof-conv` | HPROF converter |
| `e2fsdroid` | ext4 filesystem tool |
| `mke2fs` | ext4 filesystem creator |
| `make_f2fs` | F2FS filesystem creator |
| `make_f2fs_casefold` | F2FS filesystem creator (with casefolding) |
| `sload_f2fs` | F2FS filesystem loader |

### others
| Binary | Description |
|--------|-------------|
| `veridex` | DEX file verifier |

## Flutter Integration

For Flutter APK builds on Linux ARM64:

1. `aapt2` override: Set `android.aapt2FromMavenOverride=<path>` in gradle.properties
2. Build-tools: Place in `$ANDROID_SDK/build-tools/<version>/`
3. Platform-tools: Place `adb` in `$ANDROID_SDK/platform-tools/`
4. NDK shim: Flutter requires NDK for `llvm-strip`; create a shim directory with system `llvm-strip`

The `setup.sh` script handles all of this automatically.

## Versioning

Project versions track Android build-tools versions:
- Current target: **35.0.2** (matching `platform-tools-35.0.2` AOSP tag)
- The `TOOLS_VERSION` variable in `CMakeLists.txt` controls this
- `versions.json` is the central registry of all known versions, their verification status (`verified`/`unverified`/`shim`), AOSP tags, and release availability

### Registry and artifact rules

- A `release` field in `versions.json` means the tag **actually exists** on `soobujmiah/adt` with downloadable assets. Never register a release that has not been published — `install-*` trusts the field and downloads will otherwise 404.
- Asset naming convention, shared by `artifacts/` and release uploads: `build-tools-<version>-linux-arm64.tar.gz` and `platform-tools-<version>-linux-arm64.tar.gz`.
- Installer order for a verified version: (1) checked-in `artifacts/` tarball, SHA256-verified against `artifacts/SHA256SUMS`; (2) GitHub Release download if a `release` field exists; (3) source build.
- **Release downloads are integrity-checked before install.** The archive's SHA256 is compared against the asset `digest` reported by the GitHub Releases API (`fetch_release_asset_digest` + `verify_asset_digest`), and every expected binary's architecture is verified (`verify_payload_arch`) *before* anything is copied into `$SDK_ROOT`. The architecture check searches the whole extraction, so any tarball layout — flat `build-tools/<bin>` or a nested `android-sdk-linux-arm64/...` tree — is covered. A bad payload aborts the install and leaves the SDK untouched. When no digest is available the install continues with an explicit warning (offline use stays possible).
- **`sdkmanager` must not install `build-tools` or `platform-tools` on ARM64.** Google serves linux-x86_64 payloads for both; they install cleanly and only fail when executed. `run_sdkmanager` refuses those two packages at its single choke point — which covers every caller, including `bootstrap`, `install-profile` and `install-platforms` — and points at `install-build-tools` / `install-platform-tools` instead. Platforms, NDK, CMake and cmdline-tools are unaffected.
- **Covered by tests:** `tests/test_release_integrity.sh` (run by CI) exercises the architecture gate, the digest check and the `sdkmanager` refusal.
- When adding a new validated artifact, commit the tarball under `artifacts/` and append its SHA256 line to `artifacts/SHA256SUMS` in the same commit.

### Patch Resolution Order

When `get_source.py` applies patches for a given component and version:
1. **Version-specific first**: `patches/<component>/<version>/` (e.g. `patches/build-tools/35.0.2/`)
2. **Base fallback**: `patches/base/` (universal GCC/glibc compatibility patches)

For files in `misc/`, version-specific files override base files with the same name.

### Concrete Example: Building `build-tools 35.0.2`

When you run `./setup.sh build-build-tools 35.0.2`, here is the exact patch resolution:

**Git patches** (applied to AOSP source in `src/`):
```
patches/build-tools/35.0.2/libbase.patch   → NOT FOUND → patches/base/libbase.patch ✓
patches/build-tools/35.0.2/logging.patch   → NOT FOUND → patches/base/logging.patch ✓
patches/build-tools/35.0.2/core.patch      → NOT FOUND → patches/base/core.patch ✓
...etc for all 10 patches
```

**Misc files** (pre-generated headers/source copied into `src/`):
```
platform_tools_version.h:
  patches/build-tools/35.0.2/misc/platform_tools_version.h ✓ (version-specific WINS)
  patches/base/misc/platform_tools_version.h (ignored)

protobuf_config.h:
  patches/build-tools/35.0.2/misc/protobuf_config.h → NOT FOUND
  patches/base/misc/protobuf_config.h ✓ (base fallback)

deployagent.inc, deployagentscript.inc, etc:
  patches/build-tools/35.0.2/misc/deployagent.inc → NOT FOUND
  patches/base/misc/deployagent.inc ✓ (base fallback)
```

**For `platform-tools 35.0.2`**, the same logic applies but checks `patches/platform-tools/35.0.2/` first.

**Misc files are copied to these destinations:**
| File | Destination in `src/` |
|------|----------------------|
| `platform_tools_version.h` | `src/soong/cc/libbuildversion/include/` |
| `protobuf_config.h` | `src/protobuf/build/config.h` |
| `IncrementalProperties.sysprop.h` | `src/incremental_delivery/sysprop/include/` |
| `IncrementalProperties.sysprop.cpp` | `src/incremental_delivery/sysprop/` |
| `deployagent.inc` | `src/adb/fastdeploy/deployagent/` |
| `deployagentscript.inc` | `src/adb/fastdeploy/deployagent/` |
| `dex_operator_out.cc` | (compiled directly from `patches/base/misc/`) |

## setup.sh CLI

`setup.sh` is an SDK-manager-like CLI for managing Android SDK tools on Linux ARM64:

| Command | Description |
|---------|-------------|
| `install.sh` | One-line auto installer, not part of `setup.sh`: `curl -fsSL https://raw.githubusercontent.com/soobujmiah/adt/main/install.sh \| bash` — fetches the repo into `$ADT_DIR` (default `~/adt`; git clone, tarball fallback when git is missing) and runs `setup.sh bootstrap --auto`. Always unattended (piped stdin cannot prompt); idempotent; honors `ADT_DIR`/`ADT_REF` |
| `bootstrap` | Fresh-device full setup: `./setup.sh`/`bootstrap` = **guided** (device check first, permission per step); `bootstrap --auto` = **unattended** (defaults, no prompts). Host dependencies auto-install via apt/dnf with root or sudo; otherwise the exact root command is printed and the run stops. Phases: device/environment check → host deps → artifact-preferred tools → shims → sdkmanager + android-35 → persistent env → `doctor` → cleanup → final guide (verification always precedes the guide; cleanup is last) |
| `setup-env` | Write/update the `ANDROID_HOME` + `PATH` block in `~/.bashrc` (idempotent) |
| `cleanup` | Remove installer leftovers: own temp dirs (only `${TMPDIR:-/tmp}/adt-install.??????` — prefixed + exactly 6-char suffix, so unrelated files are never matched), `$SDK_ROOT/.temp`, source-build trees (`$SCRIPT_DIR/src` + `$SCRIPT_DIR/build`, ~2-4 GB each, only when the checkout is the build system), and `apt-get clean` when privileged. ADT keeps no daemons/caches/background state, so this is the entire "optimization" surface; also runs as bootstrap phase 7/7 |
| `list-versions` | Show all available versions with status |
| `install-build-tools <ver>` | Download pre-built (verified) or error with guidance |
| `install-platform-tools <ver>` | Same for platform-tools |
| `install-ndk <ver>` | Create NDK shim (llvm-strip -> system strip) |
| `install-cmake [ver]` | Create CMake shim (filters Android flags) |
| `install-cmd-tools` | Install sdkmanager |
| `install-platforms [pkgs]` | Install Android platforms via sdkmanager |
| `install-profile [name]` | Install a named bundle of already-verified versions from `versions.json`'s `profiles` key by calling `install-build-tools`/`install-ndk`/`install-platforms` in sequence — builds/verifies nothing new. Default/only profile: `validated` (build-tools 35.0.2 + NDK 27.2.12479018 + platforms;android-36 — see `docs/REAL_DEVICE_BUILD_VALIDATION.md`) |
| `build-build-tools <ver>` | Build from AOSP source |
| `build-platform-tools <ver>` | Build from AOSP source |
| `doctor` | Diagnose setup (checks arch per build-tools version) |
| `status` | Show what's installed |
| `setup-gradle` | Configure `android.aapt2FromMavenOverride` |

## Troubleshooting

### Installer pitfalls on ARM64 (read before installing)

- **A "successful" install can still be unusable.** Google's linux-x86_64 payloads land with the same names and exec bits as ARM64 ones and only fail when executed (`bad machine`). That is why the architecture gate runs before any copy, and why `doctor` checks the architecture of every binary it finds.
- **Never let `sdkmanager` touch build-tools/platform-tools.** Use `install-build-tools` / `install-platform-tools`; `run_sdkmanager` refuses those two packages and tells you the right command.
- **Release downloads need retries and visible errors.** In PRoot/container environments `curl` can fail against a perfectly healthy URL. `download_asset` retries (`--retry 3 --retry-all-errors`, 20 s connect timeout), falls back to `wget`, and prints the last lines of the transfer log instead of discarding stderr. If it still fails, fetch the asset by hand, compare `sha256sum` with the release asset's `digest` from the GitHub API, then extract.
- **Keep the receipts:** an install that refuses a payload says so explicitly (`the SDK is left untouched`) — check that line, not just the exit code.

### Common Build Issues

**Missing flex/bison**: `aidl` and `libsepol` require flex and bison for parser generation.

**Protobuf version mismatch**: If host protoc version is too new (>3.21.12), generated code may be incompatible with AOSP's bundled protobuf library. Always use the protoc built from `src/protobuf/`.

**zlib-ng on Fedora**: Fedora 43+ uses `zlib-ng-compat` instead of traditional zlib. This is a drop-in replacement and works transparently.

**GCC 15 warnings**: Some AOSP code may produce warnings with GCC 15. We suppress non-critical warnings via `-Wno-attributes` and similar flags.

### Verifying Binaries

```bash
# Check it's a native Linux ARM64 binary
file build/build-tools-35.0.2/bin/aapt2
# Expected: ELF 64-bit LSB executable, ARM aarch64, version 1 (SYSV), dynamically linked ...

# Check it runs
./build/build-tools-35.0.2/bin/aapt2 version
./build/build-tools-35.0.2/bin/adb version
```

# ADT Command Reference — how to use every tool

Each tool below: a short explanation, then the exact commands and what they do. After `source ~/.bashrc`, everything runs directly (all tools are on `PATH`). If something misbehaves, run `./setup.sh doctor` first — it pinpoints the broken piece.

---

## 1. adb — the main tool for talking to a device

### Connecting a device

**First, on the phone, enable Developer options (required for both USB and wireless):**
Settings → About phone → tap **Build number** 7 times → then Settings → Additional settings → **Developer options** → enable **USB debugging**.

**Over USB (direct cable):**
```bash
adb devices -l          # lists connected devices; the first time, the phone asks "Allow USB debugging?" — tap Allow
```

**Over Wi‑Fi (wireless debugging, Android 11+ — e.g. Redmi Turbo 4 Pro / Android 16):**

Both devices must be on the same Wi‑Fi. On the phone: Developer options → **Wireless debugging** ON → tap "Pair device with pairing code" — it shows an IP:port and a 6‑digit code.

```bash
adb pair 192.168.1.5:37199      # the pairing screen's IP:port; it asks for the code (the port changes every time)
```

```bash
adb connect 192.168.1.5:5555    # THEN connect to the main wireless IP:port (pairing port ≠ connect port!)
```

```bash
adb devices -l                  # verify
```
> Remember: `pair` and `connect` are separate steps using different ports — connecting to the pairing port will not work.

**Phone-to-phone or same-device (Termux → own phone):** enable wireless debugging and follow the same pair/connect steps.

### Everyday adb work

```bash
adb devices -l                          # device list (with model, transport)
adb -s emulator-5554 shell              # with multiple devices, pick one with -s
adb shell                               # enter the phone's shell (leave with exit)
adb shell getprop ro.product.model      # read the model (any prop works this way)
adb shell getprop ro.build.version.release   # Android version

adb push file.txt /sdcard/Download/     # PC → phone
adb pull /sdcard/Download/file.txt .    # phone → PC
adb install app.apk                     # install an APK
adb install -r app.apk                  # reinstall (keeps data)
adb uninstall com.example.app           # uninstall

adb logcat                              # live log (Ctrl+C to stop)
adb logcat -d > log.txt                 # save current log to a file
adb logcat *:E                          # error level only

adb shell pm list packages | grep name  # find an installed package
adb shell screencap /sdcard/s.png && adb pull /sdcard/s.png   # screenshot
adb shell input tap 540 1200            # simulate a screen tap (x y)
adb shell input keyevent KEYCODE_HOME   # press a button
# NOTE (2026-09-21): ``input tap/swipe/keyevent/text`` are operator tools — for the owner's own
# manual use. Autonomous agent interaction with an application UI is not authorized by any
# mechanism. See soobujmiah/skb -> DEC-2026-09-21-001.

adb reboot                              # reboot
adb reboot bootloader                   # enter fastboot mode
adb kill-server && adb start-server     # restart adb if it is stuck
```

**If you see "unauthorized":** unlock the phone and tap Allow; if it never appears, use Developer options → "Revoke USB debugging authorizations" and try again.

---

## 2. fastboot — bootloader-level work (careful!)

```bash
adb reboot bootloader       # first put the phone into bootloader mode
fastboot devices            # is the device visible to fastboot?
fastboot flashing unlock    # ⚠️ unlocks the bootloader — erases ALL data!
fastboot reboot             # boot back to normal
```
Flashing a wrong image can **brick the phone** — do not write anything in fastboot unless you are sure.

---

## 3. aapt2 — APK resource tool (build / inspect APKs)

```bash
aapt2 version                          # version
aapt2 dump badging app.apk             # package name, versionCode, minSdk, permissions
aapt2 dump permissions app.apk         # permission list only
aapt2 list app.apk                     # files inside the APK
```

APK **build** pipeline (compile resources → link → zipalign → apksigner sign):
```bash
aapt2 compile --dir res/ -o compiled.zip             # compile resources
aapt2 link -o app-unsigned.apk -I $ANDROID_HOME/platforms/android-35/android.jar \
    compiled.zip --manifest AndroidManifest.xml -A assets --java gen/    # link + generate R.java
zipalign -f 4 app-unsigned.apk app-aligned.apk        # 4-byte alignment (required)
```

To make Gradle projects use ADT's aapt2:
```bash
./setup.sh setup-gradle       # writes android.aapt2FromMavenOverride into gradle.properties
```

---

## 4. Remaining platform-tools / build-tools

```bash
fastboot, sqlite3, etc1tool, hprof-conv     # in platform-tools
aapt dump badging app.apk                   # aapt (legacy) — quick package info
aidl in.aidl                                # AIDL interface → Java stub
dexdump classes.dex                         # dex analysis
split-select                                # APK split selection tool
```

**APK signing (JVM tool, installed separately):**
```bash
sudo apt install apksigner
apksigner sign --ks my.keystore app-aligned.apk
apksigner verify --print-certs app.apk
```

---

## 5. sdkmanager — the official package manager (Java tool)

```bash
sdkmanager --list_installed                    # what is installed
sdkmanager --list | head -30                   # what is available
sdkmanager "platforms;android-35"              # install a platform
sdkmanager "build-tools;35.0.0"                # REFUSED on ARM64 (x86_64 payload) — use install-build-tools
sdkmanager --uninstall "platforms;android-34"  # remove old packages (saves storage)
yes | sdkmanager --licenses                    # accept licenses automatically
```
**Requires internet** — the only online-dependent part of the SDK.

**Never install or update `build-tools` / `platform-tools` with sdkmanager.** Google publishes
linux-x86_64 payloads for both; they install without error on ARM64 and then every binary fails at
exec time (`bad machine` / `cannot execute binary file`). ADT refuses those two packages on purpose
and prints the command that does work (`./setup.sh install-build-tools <version>` /
`install-platform-tools <version>`). `platforms;…`, `ndk;…`, `cmake;…`, `cmdline-tools;…` and
`--licenses` are unaffected.

---

## 6. NDK / CMake shims — C/C++ compilation

ADT's NDK "shim" means: when a build system looks for the NDK, requests are redirected to the **device's Termux clang / system tools** (x86 NDK binaries cannot run under PRoot — that is exactly why the shims exist).

**Compiling a plain C/C++ file for Android (validated on-device recipe):**
```bash
clang --target=aarch64-linux-android24 hello.c -o hello   # native binary via Termux clang
./hello                                                    # runs directly
```

**CMake projects:** `cmake` and `ninja` are installed (the shim handles the project's `find_package` compatibility) — the usual `cmake -B build -GNinja && ninja -C build` works.

The llvm-strip shim is installed automatically — nothing to do manually.

---

## 7. Environment / maintenance

```bash
echo $ANDROID_HOME                # where the SDK lives (bootstrap writes it to ~/.bashrc itself)
./setup.sh setup-env              # rewrite the env block if it got lost
./setup.sh status                 # what is installed, which versions
./setup.sh doctor                 # diagnose problems (all checks at once)
./setup.sh cleanup                # clean temp/downloads/AOSP trees (reclaims storage)
./setup.sh list-versions          # which versions exist / can be installed
```

If `ANDROID_HOME` was deleted or a new shell does not see it: `source ~/.bashrc`.

---

## 8. Symptom → quick fix table

| Symptom | Fix |
|---|---|
| `adb: command not found` | `source ~/.bashrc`; otherwise run `./setup.sh doctor` |
| `unauthorized` | Unlock the phone → Allow; otherwise revoke authorizations and retry |
| `no devices/emulators found` (wireless) | re-run `adb connect IP:PORT`; check both devices are on the same Wi‑Fi |
| Java error from sdkmanager | Java is missing — run `./setup.sh bootstrap --auto` (installs it automatically) |
| Storage full | `./setup.sh cleanup` + `sdkmanager --uninstall` for old platforms |
| build-tools / platform-tools stopped working right after `sdkmanager` | sdkmanager pulled x86_64 payloads — re-install from ADT: `./setup.sh install-build-tools <ver>` / `install-platform-tools <ver>` |
| Release download fails with a bare `Download failed` | ADT retries and prints the transfer log; if it still fails, download the asset manually and compare `sha256sum` with the release's `digest` before extracting |
| Generally odd behaviour | read `./setup.sh doctor` output — whichever check is red is the problem |
| Gradle native build fails with `Cannot run program ".../llvm-strip"` / `Exec failed, error: 2` | An NDK version's bundled host tool is x86_64 and cannot run here — run `./setup.sh doctor` to confirm which NDK version, then `./setup.sh install-ndk <version>` to install the ARM64-compatible shim, or pin `ndkVersion` in `app/build.gradle.kts` to a version `doctor` reports OK |

---
*Full setup in one line:* `curl -fsSL https://raw.githubusercontent.com/soobujmiah/adt/main/install.sh | bash`

# Opt-in Android emulator checks

These checks use a **disposable Android virtual phone**, not production or the
local `list.db`. They do not run in `uv run pytest -q` and do not replace iPhone
or physical Android acceptance. See the [device checklist](home-screen-installation.md#outstanding-real-device-acceptance-checklist).

## Local setup

On a Linux host with KVM (`emulator -accel-check` must report usable):

1. Install the [Android SDK command-line tools](https://developer.android.com/studio)
   and a Java 21 runtime outside the repo. Review/approve only applicable SDK
   terms; unrelated TV/automotive/XR licenses are not needed. With
   `ANDROID_HOME="$HOME/Android/Sdk"` and `JAVA_HOME` pointing at your runtime,
   install the relevant packages with Android CLI:

   ```bash
   android --sdk="$ANDROID_HOME" --no-metrics sdk install emulator
   android --sdk="$ANDROID_HOME" --no-metrics sdk install platform-tools
   android --sdk="$ANDROID_HOME" --no-metrics sdk install system-images/android-35/google_apis_playstore/x86_64
   ```

   Here `android` means `$ANDROID_HOME/cmdline-tools/latest/bin/android`; it
   does not need to be on your global `PATH`.
2. Create the dedicated disposable AVD and boot it with KVM:

   ```bash
   "$ANDROID_HOME/cmdline-tools/latest/bin/avdmanager" create avd -n listapp_api35 -k 'system-images;android-35;google_apis_playstore;x86_64' -d pixel_6
   "$ANDROID_HOME/emulator/emulator" -avd listapp_api35 -no-audio -gpu swiftshader -no-snapshot
   ```

   The AVD creation command runs **only once**; do not overwrite an existing
   device. `avdmanager` is the older tool used here to select the exact image
   already installed; Android CLI's `emulator create` may select another image.
3. Complete Chrome's first-run terms/privacy choices **yourself** in the emulator
   window. The tests do not press these buttons or sign in to Google. Unlock the
   virtual phone before starting a test.
4. Run the smoke check:

   ```bash
   ANDROID_HOME="$HOME/Android/Sdk" uv run python -m pytest android_tests -q -n 0
   ```

The suite starts temporary ListR servers with disposable credentials and fresh
SQLite databases, mapping *only those servers'* loopback ports into the emulator
via `adb reverse`. The first test opens a private room in Android Chrome. The
second installs from its password prompt, launches the exact home-screen icon,
checks that installation did not grant access, signs in, then reopens and reloads
the installed app to verify remembered access. It also enables airplane mode,
removes the ADB loopback mapping, and stops the disposable server to prove a
request fails; then restores all three and reloads to check recovery. ADB
loopback can stay alive through airplane mode alone, so that is not a valid
offline test. The native shortcut and standalone
activity are checked with ADB; the installed page is checked through Chrome's
debugging interface because this Android image sometimes exposes only “Web View”
in the native accessibility tree.

On the offline feature branch, a third opt-in test installs a disposable room,
waits for its IndexedDB snapshot and service-worker control, then stops the
server, removes ADB reverse, and enables airplane mode. It confirms a network
request fails, backgrounds Chrome briefly to let its localStorage flush, then
force-stops it and relaunches the installed icon without a page reload. It checks
the read-only shell displays the saved checked item and unchanged timestamp
without edit controls. It restores the connection and
checks remembered access to the online editor. This checks a cold launch, not
HTTPS cookies or a physical phone.

Tests remove port mappings and terminate servers afterward. For the dedicated
`listapp_api35` test AVD, they remove the disposable app icon **only when it is
the sole pinned Chrome shortcut**; if other Chrome shortcuts exist, leave them
untouched and clean up the test icon manually. Chrome's normal browser data is
not cleared. Tests fail (rather than skip) if the emulator is absent or Chrome's
first-run screen is unfinished. `adb -e` selects an emulator, never a phone.
Traces, if added later, must contain only disposable test data.

**Current local checks:** all three Android 15 / Chrome 124 emulator checks
passed, including cold launch and online recovery after a short background
settling period (cold-launch check passed twice). Diagnosis: force-stopping
Chrome immediately after first login/snapshot caused **all** localStorage keys,
including the room token and routing key, to disappear after relaunch, although
the IndexedDB snapshot survived. Disconnecting CDP alone did not erase the
keys; backgrounding Chrome for five seconds before force-stop preserved them.
The delay is not a readiness signal; the test asserts the token, snapshot and
online editor after relaunch. Immediate-kill durability is not established,
so do not claim it on real devices. HTTPS cookies, newer Chrome and physical
Android/iPhone behavior remain unverified. The offline-specific test belongs
to the offline feature branch, not the `main`-based test branch.

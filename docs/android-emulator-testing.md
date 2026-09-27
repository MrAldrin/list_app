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
the installed app to verify remembered access. The native shortcut and standalone
activity are checked with ADB; the installed page is checked through Chrome's
debugging interface because this Android image sometimes exposes only “Web View”
in the native accessibility tree.

Tests remove port mappings and terminate servers afterward. For the dedicated
`listapp_api35` test AVD, they remove the disposable app icon **only when it is
the sole pinned Chrome shortcut**; if other Chrome shortcuts exist, leave them
untouched and clean up the test icon manually. Chrome's normal browser data is
not cleared. Tests fail (rather than skip) if the emulator is absent or Chrome's
first-run screen is unfinished. `adb -e` selects an emulator, never a phone.
Traces, if added later, must contain only disposable test data.

**Locally verified:** two opt-in Android 15 / Chrome 124 tests passed after
Chrome's first-run setup. This proves this emulator's standalone password-prompt
install and remembered access; it does **not** prove actual airplane-mode
reconnect, cold-restart survival, HTTPS cookies, offline viewing, current Chrome
versions, or a real Android/iPhone installation. Keep offline-specific tests with
the offline feature branch or an integration change, not in this `main`-based
test branch.

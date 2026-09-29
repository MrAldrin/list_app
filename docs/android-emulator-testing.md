# Opt-in Android emulator checks

These checks use a **disposable Android virtual phone**, not production or the
local `list.db`. They do not run in `uv run pytest -q` and do not replace iPhone
or physical Android acceptance. See the [device checklist](home-screen-installation.md#real-device-acceptance-checklist).

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

   Create the AVD **only once**; do not overwrite an existing device.
3. Complete Chrome's first-run terms/privacy choices **yourself** in the emulator
   window. The tests do not press these buttons or sign in to Google. Unlock the
   virtual phone before starting a test.
4. Run the smoke check:

   ```bash
   ANDROID_HOME="$HOME/Android/Sdk" uv run python -m pytest android_tests -q -n 0
   ```

## What it checks

Two tests run against temporary ListR servers with fresh databases. Only those
servers' ports are mapped into the emulator (`adb reverse`).

- A private room opens in Android Chrome.
- Installing from the password prompt does not grant access. After sign-in,
  reopening and reloading the installed app keeps access.
- With airplane mode on, the port mapping removed and the server stopped, a
  request fails; after restoring all three, a reload recovers.

It does not cover cold restarts, HTTPS cookies, offline viewing, or real
phones. Keep offline-specific tests with the future offline feature.

## Cleanup and safety

- Port mappings and servers are removed afterwards.
- The test icon is removed only if it is the sole pinned Chrome shortcut on the
  `listapp_api35` AVD; otherwise remove it by hand. Chrome data is not cleared.
- Tests fail (not skip) if the emulator is missing or Chrome's first-run screen
  is unfinished. `adb -e` targets the emulator, never a phone.

How the checks work and past results are in
[background](background/android-emulator-testing.md).

# Android emulator tests: implementation notes and results

Supporting detail for the [Android emulator checks](../android-emulator-testing.md).

## How the checks work

- The install test launches the exact home-screen icon, confirms it opened
  without access, signs in, then reopens and reloads the installed app.
- The offline step turns on airplane mode **and** removes the ADB loopback
  mapping **and** stops the server. ADB loopback survives airplane mode on its
  own, so airplane mode alone is not a valid offline test.
- The native shortcut and standalone activity are checked with ADB. The
  installed page is checked through Chrome's debugging interface, because this
  Android image sometimes shows only "Web View" in its accessibility tree.
- `avdmanager` is used instead of Android CLI's `emulator create` because it
  selects the exact installed system image.

## Past results

Two tests passed on Android 15 / Chrome 124 after Chrome's first-run setup.
This showed standalone install from the password prompt, remembered access, a
failed request during airplane mode plus server outage, and recovery after
reconnecting, on this emulator only.

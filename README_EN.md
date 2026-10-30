<div align="center">

[![Platform](https://img.shields.io/badge/platform-Windows%2010%20%2F%2011-0078D6?style=flat-square)](https://github.com/kun-qaq/wireless-battery-tray)
[![Release](https://img.shields.io/github/v/release/kun-qaq/wireless-battery-tray?style=flat-square&color=2ea043)](https://github.com/kun-qaq/wireless-battery-tray/releases)
[![Driver](https://img.shields.io/badge/driver-not%20required-9f7aea?style=flat-square)](https://github.com/kun-qaq/wireless-battery-tray)
[![License: MIT](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)

**English** · [简体中文](README.md)

</div>

# WirelessBatteryTray — Battery Monitor for 2.4G Wireless Devices

A Windows system-tray utility that reads the battery level of 2.4G wireless devices **directly over HID — no vendor driver needed**. Hover the tray icon and the levels are right there.

It ships with Akko S9 Ultra, Lingbao K98 and Logitech G304, but **those are just three examples**. The read logic is organized as "VID/PID + HID read method", so **any 2.4G wireless device can be added**.

**Prefer a ready-to-run binary?** Grab `WirelessBatteryTray.exe` from [Releases](https://github.com/kun-qaq/wireless-battery-tray/releases) — double-click, no Python needed.

## Features

- **No driver required**: talks HID directly; Logitech G HUB / Akko software may stay installed or be removed entirely
- **Hover to read**: no window to open, one hover shows every device
- **Color tells you when to charge**: the petal color reflects the *lowest* battery across all devices
- **Extensible**: adding a device means writing one reader class — no changes to the UI, tray or autostart code
- **Start with Windows**: one right-click toggle, three fallback mechanisms
- **Single instance**: launching it again will never spawn a second tray icon

## Table of Contents

- [Built-in Devices](#builtin-devices)
- [Usage](#usage)
- [Icon Color](#icon-color)
- [FAQ](#faq)
- [Autostart](#autostart)
- [Build from Source](#build)
- [Project Layout](#layout)
- [Adding Your Own Device](#add-device)
- [Disclaimer](#disclaimer)
- [License](#license)

---

<a id="builtin-devices"></a>

## Built-in Devices (Examples Only)

| Device | Link | How it is read |
|---|---|---|
| Akko S9 Ultra headset | GTAI 2.4G dongle (USB VID `36EB` PID `1087`) | Send a query to the HID vendor interface; byte 4 of the reply is the battery % |
| Lingbao K98 keyboard | Compx/BY solution (USB VID `3554` PID `FA09`) | Send an `0x13` command to make the device push a battery frame; byte 6 is the battery % |
| Logitech G304 mouse | LIGHTSPEED receiver (USB VID `046D` PID `C53F`) | Standard HID++ 2.0 battery feature `0x1000` |

Devices are matched by **VID/PID**. Same-model devices usually work out of the box; a different production batch may use a different chipset and therefore a different PID.

<a id="usage"></a>

## Usage

1. Run `WirelessBatteryTray.exe` — a cherry blossom icon appears in the tray overflow area (bottom-right).
2. **Hover** the icon → one line with all devices, e.g. `Headset 81% | Keyboard 100% | Mouse 90%`
3. **Left-click** → detail window with battery bars and percentages
4. **Right-click** → menu: Show details / Refresh now / Start with Windows / Quit

<a id="icon-color"></a>

## Icon Color = "Should I Charge It?"

The tray icon is a cherry blossom; **its petal color reflects the lowest battery among all devices**, so you can tell at a glance without opening anything.

| Petal color | Meaning | Suggested action |
|---|---|---|
| Pink | Lowest level > 30% | Fine, keep using |
| Amber | Lowest level 15% ~ 30% | Charge it soon |
| Red | Lowest level ≤ 15% | Charge now |
| Gray | Not read yet / device offline | Check the device power switch |

The **lowest** value wins — one nearly-empty device always shows up in the petal color instead of being masked by two full ones. Hover or open the window to see which device it is.

Thresholds live in `sakura.py` (`PALETTES` and `palette_for()`) if you prefer 40%/20% or anything else.

<a id="faq"></a>

## FAQ

**The blossom turned yellow/red — is something broken?**
No. It means one device dropped below 30% (amber) or 15% (red). It is a charge reminder, not an error. Hover the icon to see which device.

**A device shows "offline" — is that a bug?**
No. A sleeping or powered-off mouse is reported as absent by the receiver; that is normal power saving. Move the mouse and it comes back — the app retries every 8 seconds until it does.

**Everything shows "offline" right after logging in?**
Expected. USB receivers need a moment to enumerate. On autostart the app deliberately waits 15 seconds before the first read, and keeps retrying anyway.

**Does it conflict with the vendor drivers?**
No. Logitech is a plain read, Akko sends a single query, and Lingbao sends a single status query — none of them change any setting. Keep the official drivers installed, or uninstall them entirely.

**Why is the keyboard not stuck at a round 100%?**
The `0x64` (=100) values inside the K98 feature report `0x06` are **fixed firmware parameters, not the battery level** — reading them shows 100% forever. The real level lives in the `13 0A` frame the device pushes on its own (e.g. `13 0a 01 00 04 05 62 10` → `04 05` is 4.05 V, `0x62` is 98%). The app sends one `0x05` status query to make the device push that frame immediately, so you see real values like 95% or 99%.

**Refresh rate?**
Every 30 seconds in the background, automatically shortened to 8 seconds while any device is unreachable. "Refresh now" forces an update.

<a id="autostart"></a>

## Autostart

Right-click the tray icon → **Start with Windows**. Three mechanisms are tried in order, and the first success wins (the others are cleaned up so nothing starts twice):

1. **Scheduled task** (best): triggered at logon with a 15 s delay, retries 3 times on failure
2. **Startup folder shortcut**: carries `--startup`, the app waits 15 s itself
3. **`HKCU\...\Run`** registry value: last-resort fallback

Single-instance protection (kernel mutex) means launching it again will not create a second tray icon. If you move the exe, the autostart entry is repaired on the next launch.

<a id="build"></a>

## Build from Source

```bash
# dependencies
pip install hidapi pystray pillow pywin32

# run
python wireless_battery_tray.py

# build a single-file exe (--icon must be an ABSOLUTE path,
# otherwise it is resolved relative to the spec directory)
pyinstaller --onefile --noconsole --icon "D:/path/to/sakura.ico" \
            --name WirelessBatteryTray wireless_battery_tray.py
```

<a id="layout"></a>

## Project Layout

```
wireless_battery_tray.py   main app (HID reading + tray UI + autostart integration)
sakura.py                  cherry blossom icon drawing (color follows lowest battery)
sakura.ico                 exe icon (16~256 px)
autostart.py               autostart manager (scheduled task / startup folder / Run key)
selftest.py                CLI self-test, prints all battery levels
probe_*.py                 RE probing scripts, useful when adding devices
tools/                     frida hooking, string extraction and other RE helpers
```

<a id="add-device"></a>

## Adding Your Own Device

You do not need to touch the UI, tray or autostart code — **just add a reader class**:

1. `enum_hid.py` — find the device's VID/PID and vendor interface
2. `probe_descriptor.py` — parse the HID report descriptor to see which reports exist (a read-only feature report is the easiest case)
3. If the protocol is proprietary, run the vendor driver and capture its traffic with `tools/hid_hook.py` (frida), then copy what it sends
4. Write a `XxxReader` class modelled on `G304Reader` / `K98Reader` and append it to `READERS`

Devices speaking a public protocol can reuse existing templates (Logitech HID++, Bluetooth HID battery usage page). PRs adding new devices are welcome.

<a id="disclaimer"></a>

## Disclaimer

This project reads battery levels by reverse-engineering the HID communication of vendor drivers. It is for personal learning and device management only. All protocols used here are undocumented and may break after a firmware update. Not affiliated with any manufacturer.

<a id="license"></a>

## License

Released under the **MIT License**. See [LICENSE](LICENSE) for the full text.

Copyright (c) 2026 kun-qaq

You are free to use, copy, modify, merge, publish, distribute, sublicense and sell copies of this software, provided the copyright notice and this permission notice are included. The software is provided "as is", without warranty of any kind.

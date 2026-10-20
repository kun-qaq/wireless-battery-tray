# WirelessBatteryTray — Battery Monitor for 2.4G Wireless Devices

A Windows system-tray utility that reads the battery level of 2.4G wireless devices **directly over HID — no vendor driver needed**. Hover the tray icon and the levels are right there.

It ships with Akko S9 Ultra, Lingbao K98 and Logitech G304, but **those are just three examples**. The read logic is organized as "VID/PID + HID read method", so **any 2.4G wireless device can be added** — see [Adding Your Own Device](#adding-your-own-device).

> 中文版请见 [README.md](README.md) — Chinese version.

Platform: Windows 10 / 11

## Built-in Devices (Examples Only)

| Device | Link | How it is read |
|---|---|---|
| Akko S9 Ultra headset | GTAI 2.4G dongle (USB VID `36EB` PID `1087`) | Send a query to the HID vendor interface; byte 4 of the reply is the battery % |
| Lingbao K98 keyboard | Compx/BY solution (USB VID `3554` PID `FA09`) | Read-only feature report `0x06`; byte 3 is the battery % |
| Logitech G304 mouse | LIGHTSPEED receiver (USB VID `046D` PID `C53F`) | Standard HID++ 2.0 battery feature `0x1000` |

Devices are matched by **VID/PID**. Same-model devices usually work out of the box; a different production batch may use a different chipset and therefore a different PID.

## Usage

1. Run `WirelessBatteryTray.exe` — a cherry blossom icon appears in the tray overflow area (bottom-right).
2. **Hover** the icon → one line with all devices, e.g. `Headset 81% | Keyboard 100% | Mouse 90%`
3. **Left-click** → detail window with battery bars and percentages
4. **Right-click** → menu: Show details / Refresh now / Start with Windows / Quit

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

## FAQ

**The blossom turned yellow/red — is something broken?**
No. It means one device dropped below 30% (amber) or 15% (red). It is a charge reminder, not an error. Hover the icon to see which device.

**A device shows "offline" — is that a bug?**
No. A sleeping or powered-off mouse is reported as absent by the receiver; that is normal power saving. Move the mouse and it comes back — the app retries every 8 seconds until it does.

**Everything shows "offline" right after logging in?**
Expected. USB receivers need a moment to enumerate. On autostart the app deliberately waits 15 seconds before the first read, and keeps retrying anyway.

**Does it conflict with the vendor drivers?**
No. Reads are non-destructive (Logitech/Lingbao are plain reads; the Akko query does not affect playback). Keep the official drivers installed, or uninstall them entirely.

**Refresh rate?**
Every 30 seconds in the background, automatically shortened to 8 seconds while any device is unreachable. "Refresh now" forces an update.

## Autostart

Right-click the tray icon → **Start with Windows**. Three mechanisms are tried in order, and the first success wins (the others are cleaned up so nothing starts twice):

1. **Scheduled task** (best): triggered at logon with a 15 s delay, retries 3 times on failure
2. **Startup folder shortcut**: carries `--startup`, the app waits 15 s itself
3. **`HKCU\...\Run`** registry value: last-resort fallback

Single-instance protection (kernel mutex) means launching it again will not create a second tray icon. If you move the exe, the autostart entry is repaired on the next launch.

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

## Adding Your Own Device

You do not need to touch the UI, tray or autostart code — **just add a reader class**:

1. `enum_hid.py` — find the device's VID/PID and vendor interface
2. `probe_descriptor.py` — parse the HID report descriptor to see which reports exist (a read-only feature report is the easiest case)
3. If the protocol is proprietary, run the vendor driver and capture its traffic with `tools/hid_hook.py` (frida), then copy what it sends
4. Write a `XxxReader` class modelled on `G304Reader` / `K98Reader` and append it to `READERS`

Devices speaking a public protocol can reuse existing templates (Logitech HID++, Bluetooth HID battery usage page). PRs adding new devices are welcome.

## Disclaimer

This project reads battery levels by reverse-engineering the HID communication of vendor drivers. It is for personal learning and device management only. All protocols used here are undocumented and may break after a firmware update. Not affiliated with any manufacturer.

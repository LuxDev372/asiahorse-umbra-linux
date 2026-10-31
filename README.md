# AsiaHorse Umbra ARGB Hub — Linux Control

Native Linux control for the **AsiaHorse Umbra ARGB hub** (USB `1a86:fe05`,
enumerates as "USBFAN", QinHeng CH55x chip). AsiaHorse ships no Linux
software and OpenRGB does not support this hub — this tool speaks its HID
protocol directly through `/dev/hidraw`. The CLI uses the Python 3 standard library only; the desktop GUI also requires Tk.

Verified working August 2026: full-color control of 124 LEDs across 10
ports on real hardware.

## Quick start

```bash
# one-time: let your user talk to the hub (then replug or: sudo udevadm trigger)
sudo cp 70-asiahorse.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger

python3 asiahorse.py status          # read-only sanity check
python3 asiahorse.py topology        # per-port LED counts
python3 asiahorse.py color 113 230 207
python3 asiahorse.py off
```

## Desktop GUI

A native English-language Linux desktop app with five lighting effects:
**Solid color**, **Breathing**, **Rainbow**, **Color cycle** and **Chase**.
Includes color selection, brightness and speed controls, start/stop, and
read-only temperature and fan-speed monitoring. No pip packages are required.

### Install and launch

Download and extract the entire repository (or clone it), keeping all Python
files together. Install the Tk package for your distribution:

```sh
# Bazzite: install, then reboot before launching
sudo rpm-ostree install python3-tkinter

# Fedora Workstation
sudo dnf install python3-tkinter

# Debian / Ubuntu
sudo apt install python3-tk
```

Run only the command for your distribution. From the project folder, install
the USB permission rule once:

```sh
sudo cp 70-asiahorse.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=hidraw
```

The rule grants access to the active local desktop user via `uaccess`, without
requiring a `plugdev` group. Reconnect the hub USB connection if permissions
have not taken effect. Run the app as your regular user:

```sh
python3 asiahorse_gui.py
```

### Using effects

1. Select an effect and choose a color.
2. Adjust brightness and speed, then press **Start / apply**.
3. Press **Start / apply** again after changing settings.

The selected color applies to solid color, breathing and chase. Rainbow and
color cycle generate their own colors. At 1× speed, one cycle takes four
seconds; speed ranges from 0.25× to 3×. Effects repeat independently along
each port's detected LED chain. All ports share the same settings; physical
fan geometry and separate per-port settings are not configured in this version.

**Stop** freezes the last frame. **Turn off RGB** sends black. Closing the
app stops streaming and leaves the last frame latched. Animated effects require
the app to stay open, streaming at up to approximately 20 frames/second.
Do not run another RGB controller or a second app instance at the same time.
No boot effects or firmware presets are modified.

### Sensor readings

Temperature and fan speed readings refresh every two seconds from Linux
`/sys/class/hwmon`. Sources and sensor labels are shown alongside readings.
These are system sensors, **not telemetry decoded from the Umbra hub**.
Only sensors exposed by installed kernel drivers appear. A fan connected only
to the hub may have no RPM reading. Missing or faulty readings show
**Unavailable**, while an actual zero RPM reading is shown as zero.
Sensor access is read-only: the app does not control fan speed or cooling policy.

### Validation and troubleshooting

All five effects were reported working by the project user on an Umbra hub
running Bazzite. Compatibility with other hardware configurations is not yet
established. The English UI translation needs a desktop visual check; this
build environment has no working Tk display or attached hub.

- **Permission denied:** install the `70-asiahorse.rules` rule above and reconnect USB.
- **No hub found:** check the USB data cable and the hub's power connection.
- **No LEDs detected:** check connected lighting devices; the GUI refuses to guess LED counts.
- **No sensors:** only readings provided by your system's hwmon drivers can appear.

Run backend tests without a USB device or desktop:

```sh
python3 -m unittest discover -s tests -v
```

The worker keeps one USB connection open during playback and handles the
hub's software-mode re-enumeration using the existing driver. Tests cover
animation values, packet numbering/padding/checksums, worker lifecycle and
sensor parsing.

## Protocol documentation

Everything below was cross-validated from two independent sources (a
Wireshark capture and a published SignalRGB plugin) plus live testing;
the checksum math reproduces both sources byte-for-byte.

**Transport:** USB HID, 65-byte output reports = report ID `0x00` + 64-byte
payload, zero-padded.

**Checksum:** 8-bit additive over all preceding packet bytes:
`sum = (sum + byte) & 0xFF`, appended as the final meaningful byte.

**Native command packet:**

```
52 42 <len> 00 <body...> <checksum>      len = body length + 5
```

| Body      | Meaning                                          |
|-----------|--------------------------------------------------|
| `00`      | Status query (hub replies with a `52 42` frame)  |
| `01 FF`   | Topology query (reply below)                     |
| `FD 01`   | Enter software-controlled RGB mode (see quirks!) |
| `08 00`   | Motherboard passthrough "on" (per the capture)   |
| `08 01`   | Motherboard passthrough "off"                    |

**Topology reply:** ten 5-byte records starting at offset 6:
`[led_count, ?, ?, port_index, ?]` for ports 0–9.

**Direct RGB streaming packet:**

```
88 <packet_count> <packet_index> <20 x R,G,B> <checksum>
```

Frame = all ports' LEDs concatenated in port order 0–9, padded with black
to `packet_count * 20` slots. `packet_count = ceil(total_leds / 20)`.

## Hard-won quirks (read before coding against this)

1. **The packet index is 1-BASED.** Sending index 0 makes the firmware
   drop off the USB bus entirely. This cost us an evening.
2. **`FD 01` (software mode) makes the hub re-enumerate.** It disappears
   from USB and returns, possibly under a different hidraw node — and the
   *old* node can linger briefly, so a quick reopen can grab a corpse.
   Reopen and **ping with a status query until it answers** before
   streaming ("proof of life before paint").
3. **Colors latch.** The hub holds the last streamed frame indefinitely
   with zero refresh — event-driven control works fine. Power loss resets
   to the hub's built-in effects (a warm reboot does not: the hub is
   SATA-powered).
4. **The diodes have no gamma.** High-brightness mixed colors wash toward
   white; run saturated colors dark (true amber ≈ `200,110,10`, not
   `245,189,99`).
5. **Return-to-hardware-effects command: unknown.** `FD 00` is untried.
   A full power cycle restores the hub's own effects.
6. **The pip `hidapi` wheel may use the libusb backend**, which ignores
   hidraw permissions and fails to open the device. This tool avoids the
   problem by using `/dev/hidraw` directly — no dependencies.

## Credits

- **u/idk_a_name_wtf** (r/ASIAHORSEGlobal) — original Wireshark capture
  of the passthrough packets, proving the hub could be spoken to at all.
- **maihcx** — [SignalRGB plugin](https://github.com/maihcx/AsiaHorse-Umbra-ARGB-Hub-SignalRGB-Plugin)
  documenting the full protocol.
- **ToeTagger** — found the sources, supplied the hardware, eyeballed
  every color; a guy in Arkansas who wouldn't stop digging. Linux port
  and quirk hunting with **Claude**.

MIT licensed. If you port this into OpenRGB proper, the protocol notes
above are yours — that's the point.

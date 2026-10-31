"""Deterministic LED effects and a single-owner USB animation worker."""
import colorsys
import math
import queue
import threading
import time
from dataclasses import dataclass

import asiahorse as usb

EFFECTS = ("Solid color", "Breathing", "Rainbow", "Color cycle", "Chase")


@dataclass(frozen=True)
class Settings:
    effect: str = "Solid color"
    color: tuple = (113, 230, 207)
    brightness: float = 0.7
    speed: float = 1.0


def make_frame(ports, settings, elapsed):
    """Repeat the effect independently on each port; speed = cycles / 4 seconds."""
    if settings.effect not in EFFECTS:
        raise ValueError("Unknown effect")
    phase = elapsed * settings.speed / 4
    level = max(0, min(1, settings.brightness))
    frame = []
    for count in ports:
        for led in range(count):
            gain = 1
            rgb = settings.color
            if settings.effect == "Breathing":
                gain = (1 + math.cos(phase * math.tau)) / 2
            elif settings.effect == "Rainbow":
                rgb = tuple(255 * c for c in colorsys.hsv_to_rgb((led / count - phase) % 1, 1, 1))
            elif settings.effect == "Color cycle":
                rgb = tuple(255 * c for c in colorsys.hsv_to_rgb(phase % 1, 1, 1))
            elif settings.effect == "Chase":
                # A bright head and fading tail, wrapping around each LED chain.
                distance = (phase * count - led) % count
                gain = max(0, 1 - distance / max(1, count / 4))
            frame.append(tuple(max(0, min(255, round(c * level * gain))) for c in rgb))
    return frame


def send_frame(hub, colors):
    if not colors:
        raise ValueError("No LEDs detected")
    count = math.ceil(len(colors) / usb.LEDS_PER_PACKET)
    if count > 255:
        raise ValueError("Too many LEDs")
    for index in range(count):
        chunk = colors[index * 20:(index + 1) * 20]
        chunk += [(0, 0, 0)] * (20 - len(chunk))
        # Never send index 0: this firmware drops off the bus.
        written = usb.write(hub, usb.rgb_packet(count, index + 1, chunk))
        if written != usb.PAYLOAD + 1:
            raise OSError("Incomplete USB write")


class Player:
    """Only this worker touches HID. Tk communicates through queues."""
    def __init__(self):
        self.events = queue.Queue()
        self.commands = queue.Queue()
        self.closing = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def start(self, settings):
        self.commands.put(("start", settings))

    def stop(self):
        self.commands.put(("stop", None))

    def off(self):
        self.start(Settings(brightness=0))

    def close(self):
        self.closing.set()
        self.commands.put(("close", None))

    def _connect(self):
        hub = usb.open_hub()
        try:
            ports = usb.topology(hub)
            if not sum(ports):
                raise RuntimeError("Could not read LED counts. Check the hub connections.")
            usb.write(hub, usb.native(bytes([0xFD, 0x01])))
        finally:
            hub.close()
        if self.closing.wait(0.5):
            return None, ports
        hub = usb.stabilize()
        return hub, ports

    def _run(self):
        hub = None
        settings = None
        ports = []
        start = 0
        repeats = 0
        try:
            while not self.closing.is_set():
                try:
                    command, value = self.commands.get(timeout=0.05 if settings else 0.2)
                    # Collapse rapid clicks to the latest requested state.
                    while not self.commands.empty():
                        command, value = self.commands.get_nowait()
                except queue.Empty:
                    command = None
                if command == "close":
                    break
                if command == "stop":
                    settings = None
                    self.events.put("Stopped · last frame stays lit. Use Turn off RGB to switch off.")
                elif command == "start":
                    settings = value
                    start = time.monotonic()
                    repeats = 0
                if settings is None:
                    continue
                try:
                    if hub is None:
                        self.events.put("Connecting to hub…")
                        hub, ports = self._connect()
                        start = time.monotonic()
                        if hub is None:
                            break
                    if self.closing.is_set():
                        break
                    send_frame(hub, make_frame(ports, settings, time.monotonic() - start))
                    repeats += 1
                    if repeats == 1:
                        self.events.put(f"{settings.effect} · {sum(ports)} LED · {sum(n > 0 for n in ports)} ports")
                    # Match the original driver's repeated delivery for latched colors.
                    if settings.effect == "Solid color" and repeats >= 5:
                        settings = None
                except (OSError, RuntimeError, ValueError, SystemExit) as exc:
                    self.events.put(f"Could not control hub: {exc}")
                    settings = None
                    if hub is not None:
                        hub.close()
                        hub = None
        finally:
            if hub is not None:
                hub.close()

"""Read-only Linux hwmon telemetry. No assumptions about hub port mapping."""
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Sensor:
    key: str
    source: str
    label: str
    kind: str
    value: float | None


def _read(path: Path, fallback: str = "") -> str:
    try:
        return path.read_text().strip()
    except OSError:
        return fallback


def read_sensors(root: Path = Path("/sys/class/hwmon")) -> list[Sensor]:
    sensors = []
    for device in sorted(root.glob("hwmon*")):
        source = _read(device / "name", device.name)
        for prefix, kind, scale in (("temp", "temperature", 1000), ("fan", "fan", 1)):
            for path in sorted(device.glob(f"{prefix}[0-9]*_input")):
                stem = path.name.removesuffix("_input")
                label = _read(device / f"{stem}_label", stem) or stem
                try:
                    value = int(path.read_text().strip()) / scale
                    if _read(device / f"{stem}_fault") == "1":
                        value = None
                except (OSError, ValueError):
                    value = None
                sensors.append(Sensor(str(path), source, label, kind, value))
    return sensors

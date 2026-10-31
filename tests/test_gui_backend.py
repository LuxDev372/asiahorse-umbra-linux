import tempfile
import unittest
from pathlib import Path

from sensors import read_sensors


class SensorsTest(unittest.TestCase):
    def test_readings_labels_faults_and_invalid_data(self):
        with tempfile.TemporaryDirectory() as folder:
            device = Path(folder) / "hwmon0"
            device.mkdir()
            for name, value in {"name": "chip", "temp1_input": "42500",
                                "temp1_label": "CPU", "fan1_input": "0",
                                "fan2_input": "1200", "fan2_fault": "1",
                                "temp2_input": "bad"}.items():
                (device / name).write_text(value)
            sensors = {s.label: s for s in read_sensors(Path(folder))}
            self.assertEqual(sensors["CPU"].value, 42.5)
            self.assertEqual(sensors["CPU"].source, "chip")
            self.assertEqual(sensors["fan1"].value, 0)
            self.assertIsNone(sensors["fan2"].value)
            self.assertIsNone(sensors["temp2"].value)

    def test_missing_root(self):
        self.assertEqual(read_sensors(Path("/nonexistent/hwmon")), [])


if __name__ == "__main__":
    unittest.main()

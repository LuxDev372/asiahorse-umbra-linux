import threading
import unittest
from unittest.mock import Mock, patch

import effects
from effects import EFFECTS, Player, Settings, make_frame, send_frame


class EffectTests(unittest.TestCase):
    def test_effects_dimensions_limits_and_time(self):
        for effect in EFFECTS:
            with self.subTest(effect=effect):
                settings = Settings(effect=effect)
                first = make_frame([0, 12, 24], settings, 0)
                later = make_frame([0, 12, 24], settings, 0.7)
                self.assertEqual(len(first), 36)
                self.assertTrue(all(isinstance(v, int) and 0 <= v <= 255 for rgb in later for v in rgb))
                if effect == "Solid color":
                    self.assertEqual(first, later)
                else:
                    self.assertNotEqual(first, later)
                self.assertTrue(all(rgb == (0, 0, 0) for rgb in make_frame([12], Settings(effect, brightness=0), 1)))

    def test_breath_and_port_repetition(self):
        settings = Settings("Breathing", (200, 100, 50), 1, 1)
        self.assertEqual(make_frame([1], settings, 0), [(200, 100, 50)])
        self.assertEqual(make_frame([1], settings, 2), [(0, 0, 0)])
        for effect in ("Rainbow", "Chase"):
            frame = make_frame([12, 12], Settings(effect=effect), 0.5)
            self.assertEqual(frame[:12], frame[12:])

    @patch("effects.usb.write", return_value=65)
    def test_one_based_packets_padding_checksum(self, write):
        send_frame(object(), [(12, 34, 56)] * 21)
        packets = [call.args[1] for call in write.call_args_list]
        self.assertEqual(len(packets), 2)
        for index, packet in enumerate(packets, 1):
            self.assertEqual(len(packet), 64)
            self.assertEqual(packet[:3], bytes([0x88, 2, index]))
            self.assertEqual(packet[-1], sum(packet[:-1]) & 255)
        self.assertEqual(packets[1][6:63], bytes(57))

    @patch("effects.usb.write", return_value=64)
    def test_short_write_fails(self, write):
        with self.assertRaises(OSError):
            send_frame(object(), [(0, 0, 0)])

    def test_player_reuses_connection_and_closes(self):
        hub = Mock()
        sent = threading.Event()
        with patch.object(Player, "_connect", return_value=(hub, [12])) as connect, \
             patch("effects.send_frame", side_effect=lambda *args: sent.set()):
            player = Player()
            try:
                player.start(Settings(effect="Rainbow"))
                self.assertTrue(sent.wait(2))
                sent.clear()
                player.start(Settings(effect="Breathing"))
                self.assertTrue(sent.wait(2))
                self.assertEqual(connect.call_count, 1)
                player.stop()
                # A FIFO marker is delivered after stop is processed.
                message = ""
                for _ in range(10):
                    message = player.events.get(timeout=2)
                    if message.startswith("Stopped"):
                        break
                self.assertTrue(message.startswith("Stopped"))
            finally:
                player.close()
                player.thread.join(2)
            self.assertFalse(player.thread.is_alive())
            hub.close.assert_called_once()

    def test_missing_hardware_reported_without_killing_worker(self):
        with patch.object(Player, "_connect", side_effect=SystemExit("hub unplugged")):
            player = Player()
            try:
                player.start(Settings())
                self.assertEqual(player.events.get(timeout=2), "Connecting to hub…")
                self.assertIn("hub unplugged", player.events.get(timeout=2))
                self.assertTrue(player.thread.is_alive())
            finally:
                player.close()
                player.thread.join(2)

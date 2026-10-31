from pathlib import Path
import tempfile
import unittest

from install_desktop import APP_FILES, desktop_quote, install, uninstall


class DesktopInstallTests(unittest.TestCase):
    def test_install_upgrade_and_uninstall(self):
        source = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="umbra test ") as folder:
            target = Path(folder) / "data with spaces"
            launcher = install(source, target, Path("/usr/bin/python3"))
            text = launcher.read_text()
            self.assertIn("Terminal=false\n", text)
            self.assertIn('Exec="/usr/bin/python3" "', text)
            self.assertIn("Icon=asiahorse-umbra\n", text)
            for name in APP_FILES:
                self.assertEqual((target / "asiahorse-umbra" / name).read_bytes(), (source / name).read_bytes())
            self.assertTrue((target / "icons/hicolor/scalable/apps/asiahorse-umbra.svg").is_file())
            install(source, target, Path("/usr/bin/python3"))
            keep = target / "asiahorse-umbra/user-file.txt"
            keep.write_text("keep")
            uninstall(target)
            self.assertFalse(launcher.exists())
            self.assertFalse((target / "asiahorse-umbra/asiahorse_gui.py").exists())
            self.assertTrue(keep.exists())
            uninstall(target)

    def test_exec_escaping_and_line_break_rejection(self):
        self.assertEqual(desktop_quote('/tmp/with space/100%'), '"/tmp/with space/100%%"')
        self.assertEqual(desktop_quote('/tmp/$name'), '"/tmp/\\\\$name"')
        self.assertEqual(desktop_quote('/tmp/"quoted"'), '"/tmp/\\\\"quoted\\\\""')
        with self.assertRaises(ValueError):
            desktop_quote('/tmp/new\nline')

    def test_incomplete_source_does_not_modify_destination(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with self.assertRaises(FileNotFoundError):
                install(root, root / "destination", Path("/usr/bin/python3"))
            self.assertFalse((root / "destination").exists())

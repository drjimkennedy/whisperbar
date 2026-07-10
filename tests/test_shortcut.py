import unittest

from app import pynput_shortcut


class ShortcutTests(unittest.TestCase):
    def test_documented_shortcuts(self):
        self.assertEqual(pynput_shortcut("option+space"), "<alt>+<space>")
        self.assertEqual(
            pynput_shortcut("cmd+shift+space"), "<cmd>+<shift>+<space>"
        )
        self.assertEqual(pynput_shortcut("ctrl+option+d"), "<ctrl>+<alt>+d")

    def test_invalid_shortcut_is_rejected(self):
        with self.assertRaises(ValueError):
            pynput_shortcut("option+not-a-key")
        with self.assertRaises(ValueError):
            pynput_shortcut("space")


if __name__ == "__main__":
    unittest.main()

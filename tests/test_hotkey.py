import unittest

from pynput import keyboard

from nook.hotkey import GlobalHotkeyManager, parse_hotkey


class ParseHotkeyTests(unittest.TestCase):
    def test_empty_hotkey_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_hotkey("  +  ")

    def test_default_hotkey_parses_to_generic_modifiers(self):
        self.assertEqual(
            parse_hotkey("ctrl+alt+space"),
            {keyboard.Key.ctrl, keyboard.Key.alt, keyboard.Key.space},
        )


class GlobalHotkeyManagerTests(unittest.TestCase):
    def test_right_modifier_keys_trigger_default_hotkey_once(self):
        calls = []
        manager = GlobalHotkeyManager("ctrl+alt+space", lambda: calls.append(True))

        manager._on_press(keyboard.Key.ctrl_r)
        manager._on_press(keyboard.Key.alt_r)
        manager._on_press(keyboard.Key.space)
        manager._on_press(keyboard.Key.space)

        self.assertEqual(calls, [True])

    def test_hotkey_can_trigger_again_after_release(self):
        calls = []
        manager = GlobalHotkeyManager("ctrl+alt+space", lambda: calls.append(True))

        manager._on_press(keyboard.Key.ctrl_r)
        manager._on_press(keyboard.Key.alt_r)
        manager._on_press(keyboard.Key.space)
        manager._on_release(keyboard.Key.space)
        manager._on_press(keyboard.Key.space)

        self.assertEqual(calls, [True, True])

    def test_releasing_one_modifier_side_keeps_the_other_pressed(self):
        calls = []
        manager = GlobalHotkeyManager("ctrl+alt+space", lambda: calls.append(True))

        manager._on_press(keyboard.Key.ctrl_l)
        manager._on_press(keyboard.Key.ctrl_r)
        manager._on_press(keyboard.Key.alt_l)
        manager._on_press(keyboard.Key.space)
        manager._on_release(keyboard.Key.ctrl_l)
        manager._on_press(keyboard.Key.space)

        self.assertEqual(calls, [True])

        manager._on_release(keyboard.Key.ctrl_r)
        manager._on_press(keyboard.Key.ctrl_r)
        manager._on_press(keyboard.Key.space)

        self.assertEqual(calls, [True, True])


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import patch
from adapters.focus import Focus, Target


class FocusTests(unittest.TestCase):
    def test_native_tuple_selection_is_captured(self):
        from unittest.mock import MagicMock
        app = MagicMock()
        app.processIdentifier.return_value = 123
        values = {'AXFocusedWindow': 'window', 'AXFocusedUIElement': 'field',
                  'AXRole': 'AXTextArea', 'AXSubrole': None, 'AXSelectedTextRange': 'range'}
        with patch('adapters.focus.AX.AXIsProcessTrusted', return_value=True), \
             patch('adapters.focus.NSWorkspace') as workspace, \
             patch('adapters.focus.AX.AXUIElementCreateApplication'), \
             patch('adapters.focus.AX.AXUIElementSetMessagingTimeout'), \
             patch('adapters.focus.attribute', side_effect=lambda element,key: values[key]), \
             patch('adapters.focus.AX.AXUIElementIsAttributeSettable', return_value=(0, True)), \
             patch('adapters.focus.AX.AXValueGetValue', return_value=(True, (12, 0))):
            workspace.sharedWorkspace.return_value.frontmostApplication.return_value = app
            token = Focus().snapshot()
            self.assertIsNotNone(token)
            self.assertEqual(token.selection, (12, 0))

    def test_app_window_field_or_selection_change_prevents_insertion(self):
        target = Target(1, 'window', 'field', (3, 0))
        changed = [None, Target(2, 'window', 'field', (3, 0)),
                   Target(1, 'other', 'field', (3, 0)), Target(1, 'window', 'other', (3, 0)),
                   Target(1, 'window', 'field', (5, 0))]
        for current in changed:
            with self.subTest(current=current), patch.object(Focus, 'snapshot', return_value=current), \
                 patch('adapters.focus.CFEqual', side_effect=lambda a,b:a==b), \
                 patch('adapters.focus.AX.AXUIElementSetAttributeValue') as insert:
                self.assertFalse(Focus().insert(target, 'hello'))
                insert.assert_not_called()

    def test_matching_field_uses_targeted_insertion(self):
        target = Target(1, 'window', 'field', (3, 0))
        with patch.object(Focus, 'snapshot', return_value=target), \
             patch('adapters.focus.CFEqual', return_value=True), \
             patch('adapters.focus.AX.AXUIElementSetAttributeValue', return_value=0) as insert:
            self.assertTrue(Focus().insert(target, 'hello'))
            insert.assert_called_once_with('field', 'AXSelectedText', 'hello')

    def test_missing_permission_fails_closed(self):
        with patch('adapters.focus.AX.AXIsProcessTrusted', return_value=False):
            self.assertIsNone(Focus().snapshot())

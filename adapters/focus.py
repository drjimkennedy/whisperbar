"""Conservative macOS text insertion without touching the clipboard.

Keep AX objects in this adapter only. Unknown, secure, noneditable, or changed
fields require explicit Copy Last. Never infer identity from application alone.
"""
from dataclasses import dataclass
import objc
from AppKit import NSWorkspace
import ApplicationServices as AX
from CoreFoundation import CFEqual


@dataclass
class Target:
    pid: int
    window: object
    field: object
    selection: tuple


def attribute(element, name):
    error, value = AX.AXUIElementCopyAttributeValue(element, name, None)
    return value if error == 0 else None


class Focus:
    def snapshot(self):
        try:
            with objc.autorelease_pool():
                if not AX.AXIsProcessTrusted():
                    return None
                app = NSWorkspace.sharedWorkspace().frontmostApplication()
                if app is None:
                    return None
                pid = app.processIdentifier()
                root = AX.AXUIElementCreateApplication(pid)
                AX.AXUIElementSetMessagingTimeout(root, 0.2)
                window = attribute(root, 'AXFocusedWindow')
                field = attribute(root, 'AXFocusedUIElement')
                if window is None or field is None:
                    return None
                AX.AXUIElementSetMessagingTimeout(field, 0.2)
                role = attribute(field, 'AXRole')
                subrole = attribute(field, 'AXSubrole')
                if role not in ('AXTextField', 'AXTextArea', 'AXComboBox') or subrole == 'AXSecureTextField':
                    return None
                error, editable = AX.AXUIElementIsAttributeSettable(field, 'AXSelectedText', None)
                selection = attribute(field, 'AXSelectedTextRange')
                if error != 0 or not editable or selection is None:
                    return None
                ok, selected_range = AX.AXValueGetValue(selection, AX.kAXValueCFRangeType, None)
                if not ok:
                    return None
                return Target(pid, window, field, tuple(selected_range))
        except Exception:
            # Unsupported AX implementations fail closed; do not log field contents.
            return None

    def insert(self, target, text):
        current = self.snapshot()
        if target is None or current is None:
            return False
        if current.pid != target.pid or not CFEqual(current.window, target.window) or not CFEqual(current.field, target.field) or current.selection != target.selection:
            return False
        # Address the captured field directly: no global Command-V can be redirected
        # to an unrelated newly focused app. There is still a narrow AX check/set race.
        return AX.AXUIElementSetAttributeValue(target.field, 'AXSelectedText', text) == 0

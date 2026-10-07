"""Click-through status panel. Construct/update exclusively on the Cocoa main thread."""
import AppKit as A


class StatusPanel(A.NSPanel):
    def canBecomeKeyWindow(self):
        return False

    def canBecomeMainWindow(self):
        return False


class Overlay:
    def __init__(self):
        self.panel = StatusPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            A.NSMakeRect(0, 0, 440, 132), A.NSWindowStyleMaskBorderless | A.NSWindowStyleMaskNonactivatingPanel,
            A.NSBackingStoreBuffered, False)
        self.panel.setLevel_(A.NSFloatingWindowLevel)
        self.panel.setCollectionBehavior_(A.NSWindowCollectionBehaviorCanJoinAllSpaces |
                                          A.NSWindowCollectionBehaviorFullScreenAuxiliary)
        self.panel.setHidesOnDeactivate_(False)
        self.panel.setIgnoresMouseEvents_(True)
        self.panel.setReleasedWhenClosed_(False)
        self.panel.setBackgroundColor_(A.NSColor.windowBackgroundColor())
        self.panel.setHasShadow_(True)
        self.panel.setTitle_('WhisperBar status')
        view = self.panel.contentView()
        self.heading = A.NSTextField.labelWithString_('WhisperBar')
        self.heading.setFrame_(A.NSMakeRect(20, 94, 400, 24))
        self.heading.setFont_(A.NSFont.boldSystemFontOfSize_(17))
        self.detail = A.NSTextField.wrappingLabelWithString_('')
        self.detail.setFrame_(A.NSMakeRect(20, 38, 400, 50))
        self.detail.setFont_(A.NSFont.systemFontOfSize_(13))
        self.meter = A.NSProgressIndicator.alloc().initWithFrame_(A.NSMakeRect(20, 18, 400, 12))
        self.meter.setIndeterminate_(False)
        self.meter.setMinValue_(0)
        self.meter.setMaxValue_(1)
        self.meter.setAccessibilityLabel_('Microphone input level')
        for control in (self.heading, self.detail, self.meter):
            view.addSubview_(control)
        self.visible = False
        self.screen_frame = None

    def show(self, presentation):
        if not presentation.visible:
            self.hide()
            return
        self.heading.setStringValue_(presentation.title)
        self.detail.setStringValue_(presentation.detail)
        self.meter.setHidden_(not presentation.recording)
        self.meter.setDoubleValue_(presentation.level)
        screen = A.NSScreen.mainScreen()
        if screen is None:
            return
        frame = screen.visibleFrame()
        geometry = (frame.origin.x, frame.origin.y, frame.size.width, frame.size.height)
        if not self.visible or geometry != self.screen_frame:
            width = min(440, frame.size.width - 32)
            self.panel.setFrame_display_(A.NSMakeRect(frame.origin.x + (frame.size.width - width) / 2,
                                                    frame.origin.y + 28, width, 132), True)
            self.heading.setFrameSize_(A.NSMakeSize(width - 40, 24))
            self.detail.setFrameSize_(A.NSMakeSize(width - 40, 50))
            self.meter.setFrameSize_(A.NSMakeSize(width - 40, 12))
            self.screen_frame = geometry
        if not self.visible:
            # Never activate the app or call makeKey/orderFront on this surface.
            self.panel.orderFrontRegardless()
            self.visible = True

    def hide(self):
        self.panel.orderOut_(None)
        self.visible = False

    def close(self):
        self.hide()
        self.panel.close()

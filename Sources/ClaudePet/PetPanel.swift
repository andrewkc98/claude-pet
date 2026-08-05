import Cocoa

final class PetPanel: NSPanel {
    private static let width: CGFloat = PetView.spriteDisplaySize
    private static let jumpHeadroom: CGFloat = 32
    private static let height: CGFloat = PetView.spriteDisplaySize + jumpHeadroom

    private var petView: PetView?

    convenience init() {
        let size = NSSize(width: Self.width, height: Self.height)
        self.init(
            contentRect: NSRect(origin: .zero, size: size),
            styleMask: [.borderless, .nonactivatingPanel],
            backing: .buffered,
            defer: false
        )

        isOpaque = false
        backgroundColor = .clear
        hasShadow = false
        level = .floating
        collectionBehavior = [.canJoinAllSpaces, .stationary, .fullScreenAuxiliary]
        isMovableByWindowBackground = false

        let view = PetView(frame: NSRect(origin: .zero, size: size))
        view.onDragEnded = { [weak self] origin in
            self?.persistPosition(origin)
        }
        petView = view
        contentView = view
        setFrame(restoredFrame() ?? defaultFrame(), display: true)
    }

    func triggerJump() {
        petView?.triggerJump()
    }

    func setThinking() {
        petView?.setThinking()
    }

    func noteActivity() {
        petView?.noteActivity()
    }

    func setSleepTimeout(_ seconds: TimeInterval) {
        petView?.setSleepTimeout(seconds)
    }

    func toggleVisibility() {
        if isVisible {
            orderOut(nil)
        } else {
            makeKeyAndOrderFront(nil)
        }
    }

    private func persistPosition(_ origin: NSPoint) {
        guard let screen = screen ?? NSScreen.main else { return }
        PetPositionStore.save(origin: origin, on: screen)
    }

    private func restoredFrame() -> NSRect? {
        guard let origin = PetPositionStore.loadOrigin(size: NSSize(width: Self.width, height: Self.height)) else {
            return nil
        }
        return NSRect(origin: origin, size: NSSize(width: Self.width, height: Self.height))
    }

    private func defaultFrame() -> NSRect {
        guard let screen = NSScreen.main else {
            return NSRect(x: 100, y: 100, width: Self.width, height: Self.height)
        }
        let visible = screen.visibleFrame
        let origin = NSPoint(x: visible.maxX - Self.width - 100, y: visible.minY + 100)
        return NSRect(origin: origin, size: NSSize(width: Self.width, height: Self.height))
    }
}

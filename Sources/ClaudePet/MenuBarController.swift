import Cocoa

/// AppKit NSStatusItem menu, not SwiftUI's MenuBarExtra — this app boots via
/// a plain NSApplication run loop (see AppMain.swift), not the SwiftUI `App`
/// lifecycle that MenuBarExtra requires, and switching lifecycles just for
/// this would be a much bigger change than the menu itself warrants.
final class MenuBarController {
    private let statusItem: NSStatusItem
    private let menu = NSMenu()
    private let onToggleVisibility: () -> Void
    private let onSleepTimeoutChange: (TimeInterval) -> Void
    private let onQuit: () -> Void

    private let sleepTimeoutOptions: [(title: String, seconds: TimeInterval)] = [
        ("1 minute", 60),
        ("5 minutes", 5 * 60),
        ("15 minutes", 15 * 60),
        ("30 minutes", 30 * 60),
    ]
    private var selectedSleepTimeout: TimeInterval
    private var launchAtLoginItem: NSMenuItem?

    init(
        defaultSleepTimeout: TimeInterval,
        onToggleVisibility: @escaping () -> Void,
        onSleepTimeoutChange: @escaping (TimeInterval) -> Void,
        onQuit: @escaping () -> Void
    ) {
        self.selectedSleepTimeout = defaultSleepTimeout
        self.onToggleVisibility = onToggleVisibility
        self.onSleepTimeoutChange = onSleepTimeoutChange
        self.onQuit = onQuit
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        buildMenu()
    }

    private func buildMenu() {
        if let button = statusItem.button {
            if let image = NSImage(systemSymbolName: "pawprint.fill", accessibilityDescription: "ClaudePet") {
                button.image = image
            } else {
                button.title = "\u{1F43E}" // paw prints emoji fallback if the SF Symbol is unavailable
            }
        }

        let toggleItem = NSMenuItem(title: "Show/Hide Pet", action: #selector(handleToggleVisibility), keyEquivalent: "")
        toggleItem.target = self
        menu.addItem(toggleItem)

        menu.addItem(.separator())

        let sleepMenu = NSMenu()
        for option in sleepTimeoutOptions {
            let item = NSMenuItem(title: option.title, action: #selector(handleSleepTimeoutSelected(_:)), keyEquivalent: "")
            item.target = self
            item.representedObject = option.seconds
            item.state = (option.seconds == selectedSleepTimeout) ? .on : .off
            sleepMenu.addItem(item)
        }
        let sleepItem = NSMenuItem(title: "Sleep After", action: nil, keyEquivalent: "")
        sleepItem.submenu = sleepMenu
        menu.addItem(sleepItem)

        menu.addItem(.separator())

        let launchItem = NSMenuItem(title: "Launch at Login", action: #selector(handleToggleLaunchAtLogin), keyEquivalent: "")
        launchItem.target = self
        launchItem.state = LaunchAtLogin.isEnabled ? .on : .off
        menu.addItem(launchItem)
        launchAtLoginItem = launchItem

        menu.addItem(.separator())

        let quitItem = NSMenuItem(title: "Quit ClaudePet", action: #selector(handleQuit), keyEquivalent: "q")
        quitItem.target = self
        menu.addItem(quitItem)

        statusItem.menu = menu
    }

    /// Shows the same menu instance used by the status item — right-clicking
    /// the pet itself, per roadmap 1.4, rather than requiring the menu bar.
    /// Sharing the instance (not rebuilding a second one) keeps checkbox
    /// states like "Launch at Login" automatically in sync between the two.
    func popUp(at point: NSPoint, in view: NSView) {
        menu.popUp(positioning: nil, at: point, in: view)
    }

    @objc private func handleToggleVisibility() {
        onToggleVisibility()
    }

    @objc private func handleSleepTimeoutSelected(_ sender: NSMenuItem) {
        guard let seconds = sender.representedObject as? TimeInterval else { return }
        selectedSleepTimeout = seconds
        for item in sender.menu?.items ?? [] {
            item.state = (item === sender) ? .on : .off
        }
        onSleepTimeoutChange(seconds)
    }

    @objc private func handleToggleLaunchAtLogin() {
        let newValue = !LaunchAtLogin.isEnabled
        LaunchAtLogin.setEnabled(newValue)
        launchAtLoginItem?.state = LaunchAtLogin.isEnabled ? .on : .off
    }

    @objc private func handleQuit() {
        onQuit()
    }
}

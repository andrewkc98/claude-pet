import Cocoa

final class AppDelegate: NSObject, NSApplicationDelegate {
    private static let defaultSleepTimeout: TimeInterval = 5 * 60

    private var panel: PetPanel!
    private var menuBar: MenuBarController!
    private var activityToken: NSObjectProtocol?
    private var socketServer: SocketServer?
    private var coworkWatcher: CoworkWatcher?

    func applicationDidFinishLaunching(_ notification: Notification) {
        activityToken = ProcessInfo.processInfo.beginActivity(
            options: [.userInitiatedAllowingIdleSystemSleep],
            reason: "Keep pet animation running while backgrounded"
        )

        panel = PetPanel()
        panel.setSleepTimeout(Self.defaultSleepTimeout)
        panel.makeKeyAndOrderFront(nil)

        menuBar = MenuBarController(
            defaultSleepTimeout: Self.defaultSleepTimeout,
            onToggleVisibility: { [weak self] in
                self?.panel.toggleVisibility()
            },
            onSleepTimeoutChange: { [weak self] seconds in
                self?.panel.setSleepTimeout(seconds)
            },
            onQuit: {
                NSApp.terminate(nil)
            }
        )

        let socketPath = NSString(string: "~/.claudepet/pet.sock").expandingTildeInPath
        let server = SocketServer(socketPath: socketPath) { [weak self] event in
            DispatchQueue.main.async {
                self?.handle(event)
            }
        }
        server.start()
        socketServer = server

        let coworkPath = NSString(string: "~/Library/Application Support/Claude/local-agent-mode-sessions").expandingTildeInPath
        let watcher = CoworkWatcher(
            watchPath: coworkPath,
            onPromptSent: { [weak self] in
                DispatchQueue.main.async {
                    self?.panel.setThinking()
                }
            },
            onDone: { [weak self] in
                DispatchQueue.main.async {
                    self?.panel.triggerJump()
                }
            }
        )
        watcher.start()
        coworkWatcher = watcher
    }

    private func handle(_ event: PetEvent) {
        switch event.kind {
        case .done:
            panel.triggerJump()
        case .prompt, .tool:
            panel.setThinking()
        case .notify:
            panel.noteActivity()
        }
    }
}

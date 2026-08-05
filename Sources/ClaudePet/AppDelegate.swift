import Cocoa

final class AppDelegate: NSObject, NSApplicationDelegate {
    private static let defaultSleepTimeout: TimeInterval = 5 * 60

    private var panel: PetPanel!
    private var menuBar: MenuBarController!
    private var activityToken: NSObjectProtocol?
    private var socketServer: SocketServer?
    private var coworkWatcher: CoworkWatcher?
    private let errorDetector = SessionErrorDetector()

    func applicationDidFinishLaunching(_ notification: Notification) {
        activityToken = ProcessInfo.processInfo.beginActivity(
            options: [.userInitiatedAllowingIdleSystemSleep],
            reason: "Keep pet animation running while backgrounded"
        )

        installPetsendIfNeeded()

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

        panel.onRightClick = { [weak self] point, view in
            self?.menuBar.popUp(at: point, in: view)
        }

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
            onDone: { [weak self] hadError in
                DispatchQueue.main.async {
                    if hadError {
                        self?.panel.triggerFail()
                    } else {
                        self?.panel.triggerSuccess()
                    }
                }
            }
        )
        watcher.start()
        coworkWatcher = watcher
    }

    /// Copies the petsend CLI bundled in the app's Resources out to its
    /// stable, hook-referenced path. Always overwrites rather than only
    /// installing once, so an app update also updates the CLI (e.g. the
    /// transcript_path support added after petsend originally shipped) —
    /// safe on macOS to overwrite a binary while another copy of it is
    /// mid-execution from a concurrent hook invocation.
    private func installPetsendIfNeeded() {
        guard let bundledPetsend = Bundle.main.url(forResource: "petsend", withExtension: nil) else { return }

        let fm = FileManager.default
        let targetDir = NSString(string: "~/.claudepet/bin").expandingTildeInPath
        let targetPath = (targetDir as NSString).appendingPathComponent("petsend")

        try? fm.createDirectory(atPath: targetDir, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        try? fm.removeItem(atPath: targetPath)
        try? fm.copyItem(at: bundledPetsend, to: URL(fileURLWithPath: targetPath))
        try? fm.setAttributes([.posixPermissions: 0o755], ofItemAtPath: targetPath)
    }

    private func handle(_ event: PetEvent) {
        switch event.kind {
        case .done:
            handleDone(event)
        case .prompt:
            if let path = event.transcriptPath {
                errorDetector.notePromptStart(transcriptPath: path)
            }
            panel.setThinking()
        case .tool:
            panel.setThinking()
        case .notify:
            panel.triggerAlert()
        }
    }

    private func handleDone(_ event: PetEvent) {
        guard let path = event.transcriptPath else {
            // No transcript info available (e.g. a hand-run `petsend done`
            // with no piped hook payload) — default to the success reaction.
            panel.triggerSuccess()
            return
        }
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            let hadError = self?.errorDetector.hadErrorSincePromptStart(transcriptPath: path) ?? false
            DispatchQueue.main.async {
                if hadError {
                    self?.panel.triggerFail()
                } else {
                    self?.panel.triggerSuccess()
                }
            }
        }
    }
}

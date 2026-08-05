import Foundation
import CoreServices

/// Cowork doesn't honor ~/.claude/settings.json hooks (confirmed by tracing its
/// subprocess directly — it spawns its own local claude-code process, with its
/// own sandboxed $HOME under local-agent-mode-sessions/.../local_<id>/.claude/,
/// so our Stop hook never fires for it). Instead we watch its session transcript
/// JSONL files for structured turn-start/turn-completion records:
///   - {"type":"user", ...}                          → prompt sent (thinking)
///   - {"type":"assistant", message.stop_reason:
///       "end_turn", ...}                            → turn finished (success/fail)
///   - {"type":"result", ...}                         → also treated as finished
///     (seen in some audit.jsonl-style logs, kept as a second completion shape)
/// Success vs. failure is decided by scanning for a raw `"is_error":true`
/// byte marker in everything written since the last prompt — same technique
/// as SessionErrorDetector uses for the Claude Code CLI path, just tracked
/// incrementally here since this class already tails the file. We only ever
/// inspect `type`/`stop_reason` fields and this one fixed marker string;
/// message content is never read into memory beyond that, logged, or
/// transmitted.
final class CoworkWatcher {
    private let watchPath: String
    private let onPromptSent: () -> Void
    private let onDone: (Bool) -> Void

    private var stream: FSEventStreamRef?
    private var fileOffsets: [String: UInt64] = [:]
    private var errorSeenSincePrompt: [String: Bool] = [:]
    private let stateLock = NSLock()
    private let maxLineLength = 1_000_000
    private let errorMarker = Data("\"is_error\":true".utf8)

    init(watchPath: String, onPromptSent: @escaping () -> Void, onDone: @escaping (Bool) -> Void) {
        self.watchPath = watchPath
        self.onPromptSent = onPromptSent
        self.onDone = onDone
    }

    func start() {
        guard FileManager.default.fileExists(atPath: watchPath) else { return }

        var context = FSEventStreamContext(
            version: 0,
            info: Unmanaged.passUnretained(self).toOpaque(),
            retain: nil,
            release: nil,
            copyDescription: nil
        )

        let callback: FSEventStreamCallback = { _, clientInfo, _, eventPaths, _, _ in
            guard let clientInfo else { return }
            let watcher = Unmanaged<CoworkWatcher>.fromOpaque(clientInfo).takeUnretainedValue()
            let cfArray = Unmanaged<CFArray>.fromOpaque(eventPaths).takeUnretainedValue()
            guard let paths = cfArray as? [String] else { return }
            watcher.handleChangedPaths(paths)
        }

        let flags = UInt32(
            kFSEventStreamCreateFlagFileEvents |
            kFSEventStreamCreateFlagNoDefer |
            kFSEventStreamCreateFlagUseCFTypes
        )

        guard let newStream = FSEventStreamCreate(
            kCFAllocatorDefault,
            callback,
            &context,
            [watchPath] as CFArray,
            FSEventStreamEventId(kFSEventStreamEventIdSinceNow),
            1.0,
            flags
        ) else { return }

        stream = newStream
        FSEventStreamSetDispatchQueue(newStream, DispatchQueue(label: "com.andrewtucker.ClaudePet.coworkwatcher"))
        FSEventStreamStart(newStream)
    }

    func stop() {
        guard let stream else { return }
        FSEventStreamStop(stream)
        FSEventStreamInvalidate(stream)
        FSEventStreamRelease(stream)
        self.stream = nil
    }

    private func handleChangedPaths(_ paths: [String]) {
        for path in paths where path.hasSuffix(".jsonl") {
            checkForEvents(atPath: path)
        }
    }

    private func checkForEvents(atPath path: String) {
        guard let attributes = try? FileManager.default.attributesOfItem(atPath: path),
              let fileSize = attributes[.size] as? UInt64 else {
            return
        }

        stateLock.lock()
        let previousOffset = fileOffsets[path]
        stateLock.unlock()

        guard let previousOffset else {
            // First time seeing this file: start tracking from here, don't replay history.
            stateLock.lock()
            fileOffsets[path] = fileSize
            stateLock.unlock()
            return
        }

        guard fileSize > previousOffset else { return }

        guard let handle = try? FileHandle(forReadingFrom: URL(fileURLWithPath: path)) else { return }
        defer { try? handle.close() }
        try? handle.seek(toOffset: previousOffset)
        let newData = handle.readDataToEndOfFile()

        stateLock.lock()
        fileOffsets[path] = fileSize
        stateLock.unlock()

        for line in newData.split(separator: UInt8(ascii: "\n")) where line.count < maxLineLength {
            let lineData = Data(line)

            if lineData.range(of: errorMarker) != nil {
                stateLock.lock()
                errorSeenSincePrompt[path] = true
                stateLock.unlock()
            }

            guard let json = try? JSONSerialization.jsonObject(with: lineData) as? [String: Any],
                  let type = json["type"] as? String else {
                continue
            }

            if type == "user" {
                stateLock.lock()
                errorSeenSincePrompt[path] = false
                stateLock.unlock()
                onPromptSent()
            } else if isCompletionRecord(type: type, json: json) {
                stateLock.lock()
                let hadError = errorSeenSincePrompt[path] ?? false
                errorSeenSincePrompt[path] = false
                stateLock.unlock()
                onDone(hadError)
            }
        }
    }

    private func isCompletionRecord(type: String, json: [String: Any]) -> Bool {
        if type == "result" {
            return true
        }

        if type == "assistant",
           let message = json["message"] as? [String: Any],
           let stopReason = message["stop_reason"] as? String,
           stopReason == "end_turn" {
            return true
        }

        return false
    }
}

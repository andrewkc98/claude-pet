import Foundation

/// Detects whether a Claude Code CLI turn ended with any tool error.
///
/// PostToolUse hooks simply don't fire when a tool call errors (confirmed
/// empirically — a failing Bash command and a Read on a nonexistent file
/// both produced zero PostToolUse invocations). The local session transcript
/// is the only reliable signal: every tool_result content block carries
/// `"is_error":true/false`, so we snapshot the transcript's byte offset at
/// the start of each prompt and, on Stop, scan everything written since for
/// that marker. A plain byte-substring search rather than JSON parsing,
/// consistent with treating this content as untrusted — we only ever check
/// for a fixed marker string, never parse or execute anything from it.
final class SessionErrorDetector {
    private var promptStartOffsets: [String: UInt64] = [:]
    private let lock = NSLock()
    // Deliberately small: this is only used when we never saw this turn's
    // prompt start (e.g. the pet was launched or relaunched mid-turn). A
    // generous window here risks false-flagging a stale error from several
    // messages back in a long-running conversation as belonging to the
    // current turn — confirmed in testing with a multi-MB transcript.
    private let maxScanBytes: UInt64 = 200_000
    private let errorMarker = Data("\"is_error\":true".utf8)

    func notePromptStart(transcriptPath: String) {
        guard let size = fileSize(transcriptPath) else { return }
        lock.lock()
        promptStartOffsets[transcriptPath] = size
        lock.unlock()
    }

    /// True if `"is_error":true` appears anywhere in the transcript written
    /// since the most recent prompt start for this path. Falls back to
    /// scanning the last few MB if we never saw a prompt start (e.g. first
    /// turn after app launch), rather than replaying the whole file.
    func hadErrorSincePromptStart(transcriptPath: String) -> Bool {
        lock.lock()
        let startOffset = promptStartOffsets[transcriptPath]
        lock.unlock()

        guard let currentSize = fileSize(transcriptPath) else { return false }
        let offset = startOffset ?? (currentSize > maxScanBytes ? currentSize - maxScanBytes : 0)
        guard currentSize > offset else { return false }

        guard let handle = FileHandle(forReadingAtPath: transcriptPath) else { return false }
        defer { try? handle.close() }
        try? handle.seek(toOffset: offset)
        let data = handle.readDataToEndOfFile()

        return data.range(of: errorMarker) != nil
    }

    private func fileSize(_ path: String) -> UInt64? {
        try? FileManager.default.attributesOfItem(atPath: path)[.size] as? UInt64
    }
}

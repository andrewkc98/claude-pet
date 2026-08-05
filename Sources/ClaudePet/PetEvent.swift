import Foundation

enum PetEventKind: String {
    case prompt
    case tool
    case done
    case notify
}

struct PetEvent {
    let kind: PetEventKind
    let source: String?
    /// Path to the local Claude Code session transcript, when petsend was
    /// able to read one off the hook's stdin payload. Used to detect
    /// success/failure for `.done` by scanning for is_error markers —
    /// PostToolUse hooks simply don't fire when a tool call errors, so the
    /// transcript is the only reliable signal available here.
    let transcriptPath: String?

    static func decode(from data: Data) -> PetEvent? {
        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let eventString = json["event"] as? String,
              let kind = PetEventKind(rawValue: eventString) else {
            return nil
        }
        return PetEvent(
            kind: kind,
            source: json["source"] as? String,
            transcriptPath: json["transcript_path"] as? String
        )
    }
}

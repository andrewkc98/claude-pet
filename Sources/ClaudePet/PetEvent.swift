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

    static func decode(from data: Data) -> PetEvent? {
        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let eventString = json["event"] as? String,
              let kind = PetEventKind(rawValue: eventString) else {
            return nil
        }
        return PetEvent(kind: kind, source: json["source"] as? String)
    }
}

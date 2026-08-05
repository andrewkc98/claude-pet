import Cocoa

/// Position on a screen, stored as (screen UUID, fraction of visible frame)
/// rather than raw points — raw points land off-screen the moment a display
/// is reconfigured, unplugged, or has a different resolution on next launch.
struct PetPosition: Codable {
    let screenID: String
    let xFraction: Double
    let yFraction: Double
}

enum PetPositionStore {
    private static let key = "PetPosition"

    static func save(origin: NSPoint, on screen: NSScreen) {
        guard let screenID = screen.persistentID else { return }
        let visible = screen.visibleFrame
        guard visible.width > 0, visible.height > 0 else { return }

        let xFraction = Double((origin.x - visible.minX) / visible.width)
        let yFraction = Double((origin.y - visible.minY) / visible.height)
        let position = PetPosition(screenID: screenID, xFraction: xFraction, yFraction: yFraction)

        guard let data = try? JSONEncoder().encode(position) else { return }
        UserDefaults.standard.set(data, forKey: key)
    }

    /// Returns the restored origin, clamped to keep `size` fully on-screen,
    /// or nil if there's no saved position or its screen is no longer connected.
    static func loadOrigin(size: NSSize) -> NSPoint? {
        guard let data = UserDefaults.standard.data(forKey: key),
              let position = try? JSONDecoder().decode(PetPosition.self, from: data) else {
            return nil
        }
        guard let screen = NSScreen.screens.first(where: { $0.persistentID == position.screenID }) else {
            return nil
        }

        let visible = screen.visibleFrame
        var x = visible.minX + CGFloat(position.xFraction) * visible.width
        var y = visible.minY + CGFloat(position.yFraction) * visible.height

        x = min(max(x, visible.minX), visible.maxX - size.width)
        y = min(max(y, visible.minY), visible.maxY - size.height)

        return NSPoint(x: x, y: y)
    }
}

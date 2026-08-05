import CoreGraphics
import Foundation

/// Produces an eased, integer-pixel vertical offset for a jump bounce.
/// Deliberately knows nothing about sprites/frames — sprite selection during
/// a jump is driven separately (by PetView, off `progress()`), not by this.
final class JumpArc {
    private let timer: PlayOnceTimer
    private let peakHeight: CGFloat = 24

    var isActive: Bool { timer.isActive }

    init(duration: CFTimeInterval) {
        timer = PlayOnceTimer(duration: duration)
    }

    func trigger() {
        timer.trigger()
    }

    /// 0...1 progress through the jump, for driving frame selection.
    func progress() -> CGFloat {
        timer.progress()
    }

    /// Vertical offset in points, 0 at ground level, positive = up. Always an
    /// integer so the sprite stays aligned to the pixel grid.
    func currentOffset() -> Int {
        guard timer.isActive else { return 0 }
        let t = timer.progress()
        let eased = sin(Double(t) * .pi)
        return Int((eased * peakHeight).rounded())
    }
}

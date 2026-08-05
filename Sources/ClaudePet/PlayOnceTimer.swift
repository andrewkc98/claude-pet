import QuartzCore

/// Elapsed-time-based progress for a one-shot animation. Stateless aside from
/// a start time — matches JumpArc/EmoteOverlay's pattern of deriving state from
/// wall-clock time off the existing redraw loop rather than owning a Timer.
final class PlayOnceTimer {
    private(set) var isActive = false
    private var startTime: CFTimeInterval = 0
    let duration: CFTimeInterval

    init(duration: CFTimeInterval) {
        self.duration = duration
    }

    func trigger() {
        startTime = CACurrentMediaTime()
        isActive = true
    }

    /// 0...1 progress through the duration. Returns 1 once finished (and flips
    /// isActive false the first time that happens).
    func progress() -> CGFloat {
        guard isActive else { return 1 }
        let elapsed = CACurrentMediaTime() - startTime
        if elapsed >= duration {
            isActive = false
            return 1
        }
        return CGFloat(elapsed / duration)
    }
}

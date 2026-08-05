import Cocoa

final class PetView: NSView {
    static let spriteDisplaySize: CGFloat = 128

    private enum State {
        case idle
        case thinking
        case jumping
        case sleeping
        case waking
        case alerting
        case succeeding
        case failing
    }

    private enum AlertPhase {
        case transitioning
        case held
    }

    var onDragEnded: ((NSPoint) -> Void)?

    private var dragStartMouseLocation: NSPoint = .zero
    private var dragStartFrameOrigin: NSPoint = .zero

    private let idleSheet: SpriteSheet?
    private let jumpSheet: SpriteSheet?
    private let sleepSheet: SpriteSheet?
    private let wakeSheet: SpriteSheet?
    private let alertSheet: SpriteSheet?
    private let successSheet: SpriteSheet?
    private let failSheet: SpriteSheet?
    private let thinkLongSheet: SpriteSheet?

    private var frameIndex = 0
    private var animationTimer: Timer?
    private var lastIdleFrameAdvance: CFTimeInterval = 0
    private var lastSleepFrameAdvance: CFTimeInterval = 0
    private var lastThinkLongFrameAdvance: CFTimeInterval = 0
    private var thinkingStartTime: CFTimeInterval = 0
    private var isCurrentlyLongThinking = false
    private let longThinkThreshold: CFTimeInterval = 120

    private let jumpArc = JumpArc(duration: PetAnimation.jump.duration ?? 0.7)
    private let wakeTimer = PlayOnceTimer(duration: PetAnimation.wake.duration ?? 0.6)
    private let alertIntroTimer = PlayOnceTimer(duration: PetAnimation.alert.duration ?? 0.3)
    private let successTimer = PlayOnceTimer(duration: PetAnimation.success.duration ?? 0.7)
    private let failTimer = PlayOnceTimer(duration: PetAnimation.fail.duration ?? 0.7)
    private let emoteOverlay = EmoteOverlay()
    private var state: State = .idle
    private var alertPhase: AlertPhase = .transitioning
    private var alertHoldStartTime: CFTimeInterval = 0
    private let alertHoldFrameInterval: CFTimeInterval = 1.0

    private var lastActivityTime = CFAbsoluteTimeGetCurrent()
    private var sleepTimeout: TimeInterval = 5 * 60

    private static let emoteAnchor = CGPoint(x: 72, y: 96)
    // In the headroom above the 128pt sprite (sprite occupies y 0...128).
    // Same x as the thinking-dots anchor — that one's already tuned to sit
    // over the head (cat faces right), just projected up into the headroom.
    private static let alertEmoteAnchor = CGPoint(x: 72, y: 132)

    override init(frame frameRect: NSRect) {
        idleSheet = SpriteSheet(resourceName: PetAnimation.idle.resourceName, frameSize: PetAnimation.idle.frameSize)
        jumpSheet = SpriteSheet(resourceName: PetAnimation.jump.resourceName, frameSize: PetAnimation.jump.frameSize)
        sleepSheet = SpriteSheet(resourceName: PetAnimation.sleep.resourceName, frameSize: PetAnimation.sleep.frameSize)
        wakeSheet = SpriteSheet(resourceName: PetAnimation.wake.resourceName, frameSize: PetAnimation.wake.frameSize)
        alertSheet = SpriteSheet(resourceName: PetAnimation.alert.resourceName, frameSize: PetAnimation.alert.frameSize)
        successSheet = SpriteSheet(resourceName: PetAnimation.success.resourceName, frameSize: PetAnimation.success.frameSize)
        failSheet = SpriteSheet(resourceName: PetAnimation.fail.resourceName, frameSize: PetAnimation.fail.frameSize)
        thinkLongSheet = SpriteSheet(resourceName: PetAnimation.thinkLong.resourceName, frameSize: PetAnimation.thinkLong.frameSize)
        super.init(frame: frameRect)
        startAnimationTimer()
    }

    required init?(coder: NSCoder) {
        idleSheet = SpriteSheet(resourceName: PetAnimation.idle.resourceName, frameSize: PetAnimation.idle.frameSize)
        jumpSheet = SpriteSheet(resourceName: PetAnimation.jump.resourceName, frameSize: PetAnimation.jump.frameSize)
        sleepSheet = SpriteSheet(resourceName: PetAnimation.sleep.resourceName, frameSize: PetAnimation.sleep.frameSize)
        wakeSheet = SpriteSheet(resourceName: PetAnimation.wake.resourceName, frameSize: PetAnimation.wake.frameSize)
        alertSheet = SpriteSheet(resourceName: PetAnimation.alert.resourceName, frameSize: PetAnimation.alert.frameSize)
        successSheet = SpriteSheet(resourceName: PetAnimation.success.resourceName, frameSize: PetAnimation.success.frameSize)
        failSheet = SpriteSheet(resourceName: PetAnimation.fail.resourceName, frameSize: PetAnimation.fail.frameSize)
        thinkLongSheet = SpriteSheet(resourceName: PetAnimation.thinkLong.resourceName, frameSize: PetAnimation.thinkLong.frameSize)
        super.init(coder: coder)
        startAnimationTimer()
    }

    // MARK: - External triggers

    /// States representing a brief, self-terminating reaction that should be
    /// allowed to finish playing rather than getting cut short by the next
    /// prompt/tool event — which, during an active turn, can arrive within
    /// milliseconds of the reaction starting. Deliberately excludes .alerting:
    /// that one isn't self-terminating, and a genuine "needs you" alert should
    /// yield the moment real activity resumes (e.g. PostToolUse firing right
    /// after an AskUserQuestion gets answered) rather than requiring a click
    /// even though the moment it was for has clearly passed. It persists
    /// during a true block anyway, since nothing else fires while blocked.
    private var isInProtectedReaction: Bool {
        switch state {
        case .jumping, .waking, .succeeding, .failing:
            return true
        case .idle, .thinking, .sleeping, .alerting:
            return false
        }
    }

    func setThinking() {
        if state == .sleeping {
            beginWaking()
            return
        }
        lastActivityTime = CFAbsoluteTimeGetCurrent()
        guard !isInProtectedReaction else { return }
        if state != .thinking {
            // Fresh entry into thinking — start the long-think clock. Repeated
            // calls while already thinking (e.g. one per tool call) must NOT
            // reset this, or a long task never actually reaches the threshold.
            thinkingStartTime = CACurrentMediaTime()
            isCurrentlyLongThinking = false
        }
        setState(.thinking)
        // Re-assert whichever overlay is currently correct rather than always
        // .thinking — this fires on every tool call, so blindly resetting it
        // would flip long-think's slow dots back to fast on the next call.
        emoteOverlay.setKind(isCurrentlyLongThinking ? .thinkingLong : .thinking)
    }

    func triggerJump() {
        if state == .sleeping {
            beginWaking()
            return
        }
        lastActivityTime = CFAbsoluteTimeGetCurrent()
        guard state != .waking else { return }
        setState(.jumping)
        emoteOverlay.setKind(.none)
        jumpArc.trigger()
    }

    /// For events with no dedicated visual yet (e.g. a Cowork prompt-sent tick
    /// while something else is showing): still counts as activity for the sleep
    /// timer, and still wakes the pet if it's asleep.
    func noteActivity() {
        if state == .sleeping {
            beginWaking()
            return
        }
        lastActivityTime = CFAbsoluteTimeGetCurrent()
    }

    /// An alert blocks other visuals until acknowledged (clicked). Plays the
    /// frames-1-2-3 transition once, then holds on frames 3/4 with the overlay
    /// supplying the visual interest until dismissed.
    func triggerAlert() {
        if state == .sleeping {
            beginWaking()
            return
        }
        lastActivityTime = CFAbsoluteTimeGetCurrent()
        guard state != .waking else { return }
        setState(.alerting)
        alertPhase = .transitioning
        emoteOverlay.setKind(.none)
        alertIntroTimer.trigger()
    }

    /// The done-reaction for a turn that completed with no tool errors.
    func triggerSuccess() {
        if state == .sleeping {
            beginWaking()
            return
        }
        lastActivityTime = CFAbsoluteTimeGetCurrent()
        guard state != .waking else { return }
        setState(.succeeding)
        emoteOverlay.setKind(.none)
        successTimer.trigger()
    }

    /// The done-reaction for a turn where at least one tool call errored.
    func triggerFail() {
        if state == .sleeping {
            beginWaking()
            return
        }
        lastActivityTime = CFAbsoluteTimeGetCurrent()
        guard state != .waking else { return }
        setState(.failing)
        emoteOverlay.setKind(.none)
        failTimer.trigger()
    }

    func setSleepTimeout(_ seconds: TimeInterval) {
        sleepTimeout = seconds
    }

    // MARK: - State machine

    private func setState(_ newState: State) {
        guard newState != state else { return }
        state = newState
        frameIndex = 0
        let now = CACurrentMediaTime()
        lastIdleFrameAdvance = now
        lastSleepFrameAdvance = now
    }

    private func beginWaking() {
        setState(.waking)
        emoteOverlay.setKind(.none)
        wakeTimer.trigger()
        lastActivityTime = CFAbsoluteTimeGetCurrent()
    }

    private func checkSleepTimeout() {
        guard state == .idle else { return }
        let elapsed = CFAbsoluteTimeGetCurrent() - lastActivityTime
        guard elapsed >= sleepTimeout else { return }
        setState(.sleeping)
        emoteOverlay.setKind(.none)
    }

    // MARK: - Animation loop

    private func startAnimationTimer() {
        let interval = 1.0 / PetAnimation.idle.fps
        let timer = Timer(timeInterval: interval, repeats: true) { [weak self] _ in
            self?.tick()
        }
        RunLoop.main.add(timer, forMode: .common)
        animationTimer = timer
    }

    private func tick() {
        checkSleepTimeout()

        let now = CACurrentMediaTime()
        switch state {
        case .idle:
            advanceFrameIfDue(sheet: idleSheet, fps: PetAnimation.idle.fps, lastAdvance: &lastIdleFrameAdvance, now: now)
        case .thinking:
            tickThinking(now: now)
        case .sleeping:
            advanceFrameIfDue(sheet: sleepSheet, fps: PetAnimation.sleep.fps, lastAdvance: &lastSleepFrameAdvance, now: now)
        case .jumping, .waking, .alerting, .succeeding, .failing:
            break // frame index is derived from progress()/elapsed time in draw(), not ticked here
        }

        needsDisplay = true
    }

    private func tickThinking(now: CFTimeInterval) {
        let longNow = (now - thinkingStartTime) >= longThinkThreshold
        if longNow != isCurrentlyLongThinking {
            isCurrentlyLongThinking = longNow
            frameIndex = 0
            lastIdleFrameAdvance = now
            lastThinkLongFrameAdvance = now
            emoteOverlay.setKind(longNow ? .thinkingLong : .thinking)
        }

        if longNow {
            advanceFrameIfDue(sheet: thinkLongSheet, fps: PetAnimation.thinkLong.fps, lastAdvance: &lastThinkLongFrameAdvance, now: now)
        } else {
            advanceFrameIfDue(sheet: idleSheet, fps: PetAnimation.idle.fps, lastAdvance: &lastIdleFrameAdvance, now: now)
        }
    }

    /// The master timer ticks at idle's rate (fast enough for smooth arcs/
    /// overlays in other states), but each looping sheet only advances its
    /// own frame at its own configured fps — sleep.fps was previously defined
    /// and never actually consulted, so sleep always played at idle's rate.
    private func advanceFrameIfDue(sheet: SpriteSheet?, fps: Double, lastAdvance: inout CFTimeInterval, now: CFTimeInterval) {
        guard let sheet, !sheet.frames.isEmpty, fps > 0 else { return }
        let frameDuration = 1.0 / fps
        guard now - lastAdvance >= frameDuration else { return }
        frameIndex = (frameIndex + 1) % sheet.frames.count
        lastAdvance = now
    }

    override func draw(_ dirtyRect: NSRect) {
        guard let context = NSGraphicsContext.current?.cgContext else { return }

        let (sheet, drawFrameIndex, verticalOffset) = currentFrame()
        guard let sheet, !sheet.frames.isEmpty else {
            NSColor.systemRed.setFill()
            bounds.fill()
            return
        }

        let clampedIndex = min(max(drawFrameIndex, 0), sheet.frames.count - 1)
        let spriteRect = NSRect(x: 0, y: verticalOffset, width: Self.spriteDisplaySize, height: Self.spriteDisplaySize)

        context.interpolationQuality = .none
        context.draw(sheet.frames[clampedIndex], in: spriteRect)

        let baseAnchor = (state == .alerting) ? Self.alertEmoteAnchor : Self.emoteAnchor
        let anchor = CGPoint(x: baseAnchor.x, y: baseAnchor.y + verticalOffset)
        emoteOverlay.draw(in: context, anchor: anchor)
    }

    /// Resolves (sheet, frame index, vertical offset) for the current state,
    /// and advances play-once states (jumping/waking/alerting) as a side effect.
    private func currentFrame() -> (SpriteSheet?, Int, CGFloat) {
        switch state {
        case .idle:
            return (idleSheet, frameIndex, 0)

        case .thinking:
            let sheet = isCurrentlyLongThinking ? thinkLongSheet : idleSheet
            return (sheet, frameIndex, 0)

        case .sleeping:
            return (sleepSheet, frameIndex, 0)

        case .jumping:
            let offset = CGFloat(jumpArc.currentOffset())
            let progress = jumpArc.progress()
            if !jumpArc.isActive {
                setState(.idle)
            }
            let count = jumpSheet?.frames.count ?? 1
            let index = min(Int(progress * CGFloat(count)), count - 1)
            return (jumpSheet, index, offset)

        case .waking:
            let progress = wakeTimer.progress()
            if !wakeTimer.isActive {
                setState(.idle)
            }
            let count = wakeSheet?.frames.count ?? 1
            let index = min(Int(progress * CGFloat(count)), count - 1)
            return (wakeSheet, index, 0)

        case .alerting:
            return (alertSheet, alertFrameIndex(), 0)

        case .succeeding:
            let progress = successTimer.progress()
            if !successTimer.isActive {
                setState(.idle)
            }
            let count = successSheet?.frames.count ?? 1
            let index = min(Int(progress * CGFloat(count)), count - 1)
            return (successSheet, index, 0)

        case .failing:
            let progress = failTimer.progress()
            if !failTimer.isActive {
                setState(.idle)
            }
            let count = failSheet?.frames.count ?? 1
            let index = min(Int(progress * CGFloat(count)), count - 1)
            return (failSheet, index, 0)
        }
    }

    private func alertFrameIndex() -> Int {
        let count = alertSheet?.frames.count ?? 4
        switch alertPhase {
        case .transitioning:
            let progress = alertIntroTimer.progress()
            if !alertIntroTimer.isActive {
                alertPhase = .held
                alertHoldStartTime = CACurrentMediaTime()
                emoteOverlay.setKind(.notify) // pop-in, right as the transition ends
            }
            return min(Int(progress * 3), 2)
        case .held:
            let elapsed = CACurrentMediaTime() - alertHoldStartTime
            let toggled = Int(elapsed / alertHoldFrameInterval) % 2 == 0
            return toggled ? min(2, count - 1) : min(3, count - 1)
        }
    }

    // MARK: - Drag

    /// A click wakes the pet if it's asleep (handled inside triggerJump's own
    /// sleeping check); any other click jumps — including one that clears an
    /// active alert, since triggerJump() already transitions cleanly out of
    /// .alerting the same way real activity does.
    override func mouseDown(with event: NSEvent) {
        triggerJump()
        dragStartMouseLocation = NSEvent.mouseLocation
        dragStartFrameOrigin = window?.frame.origin ?? .zero
    }

    override func mouseDragged(with event: NSEvent) {
        guard let window = window else { return }
        let current = NSEvent.mouseLocation
        let dx = current.x - dragStartMouseLocation.x
        let dy = current.y - dragStartMouseLocation.y
        window.setFrameOrigin(NSPoint(x: dragStartFrameOrigin.x + dx, y: dragStartFrameOrigin.y + dy))
    }

    override func mouseUp(with event: NSEvent) {
        guard let window = window else { return }
        onDragEnded?(window.frame.origin)
    }
}

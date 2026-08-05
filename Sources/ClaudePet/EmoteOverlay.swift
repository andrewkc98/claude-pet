import CoreGraphics
import QuartzCore

enum EmoteKind: Equatable {
    case none
    case thinking
    case thinkingLong
    case sleep
    case notify
}

/// A small pixel-grid overlay (dots, "!", later Zzz) drawn above the pet's head.
/// Stateless like JumpArc — derives its current frame from elapsed wall-clock time
/// off the existing redraw loop, rather than owning its own timer. Draws procedurally
/// at integer coordinates; never touches or resamples the body sprite image.
final class EmoteOverlay {
    private(set) var kind: EmoteKind = .none
    private var startTime: CFTimeInterval = 0

    private let thinkingFPS: Double = 2.0
    private let thinkingLongFPS: Double = 0.8
    private let dotSize: CGFloat = 4
    private let dotSpacing: CGFloat = 8

    private let fillColor = CGColor(red: 0xF7 / 255.0, green: 0xF3 / 255.0, blue: 0xEE / 255.0, alpha: 1)
    private let outlineColor = CGColor(red: 0x2A / 255.0, green: 0x1A / 255.0, blue: 0x16 / 255.0, alpha: 1)

    func setKind(_ newKind: EmoteKind) {
        guard newKind != kind else { return }
        kind = newKind
        startTime = CACurrentMediaTime()
    }

    /// `anchor` is the bottom-left of the overlay's drawing area, integer point
    /// coordinates in the same space PetView draws the body sprite in.
    func draw(in context: CGContext, anchor: CGPoint) {
        switch kind {
        case .none:
            return
        case .thinking:
            drawThinkingDots(in: context, anchor: anchor, fps: thinkingFPS)
        case .thinkingLong:
            drawThinkingDots(in: context, anchor: anchor, fps: thinkingLongFPS)
        case .notify:
            drawAlertMark(in: context, anchor: anchor)
        case .sleep:
            return
        }
    }

    private func drawThinkingDots(in context: CGContext, anchor: CGPoint, fps: Double) {
        let elapsed = CACurrentMediaTime() - startTime
        let frame = Int(elapsed * fps)
        let visibleDots = (frame % 3) + 1

        for i in 0..<visibleDots {
            let x = (anchor.x + CGFloat(i) * dotSpacing).rounded()
            let y = anchor.y.rounded()
            let rect = CGRect(x: x, y: y, width: dotSize, height: dotSize)
            context.setFillColor(fillColor)
            context.fill(rect)
            context.setStrokeColor(outlineColor)
            context.setLineWidth(1)
            context.stroke(rect.insetBy(dx: 0.5, dy: 0.5))
        }
    }

    /// Pops in at t=0 (called exactly when the sprite's intro transition finishes)
    /// then bobs gently in place — the overlay is what keeps the held alert state
    /// from reading as frozen, since the sprite's own held frames barely differ.
    private func drawAlertMark(in context: CGContext, anchor: CGPoint) {
        let elapsed = CACurrentMediaTime() - startTime
        let bobOffset = CGFloat((sin(elapsed * 1.5) * 3).rounded())

        let barWidth: CGFloat = 4
        let barHeight: CGFloat = 10
        let gap: CGFloat = 2
        let dotSize: CGFloat = 4

        let x = anchor.x.rounded()
        let dotY = (anchor.y + bobOffset).rounded()
        let barY = dotY + dotSize + gap

        let dotRect = CGRect(x: x, y: dotY, width: dotSize, height: dotSize)
        let barRect = CGRect(x: x, y: barY, width: barWidth, height: barHeight)

        context.setFillColor(fillColor)
        context.fill(dotRect)
        context.fill(barRect)
        context.setStrokeColor(outlineColor)
        context.setLineWidth(1)
        context.stroke(dotRect.insetBy(dx: 0.5, dy: 0.5))
        context.stroke(barRect.insetBy(dx: 0.5, dy: 0.5))
    }
}

import CoreGraphics

struct SpriteAnimationConfig {
    let resourceName: String
    let frameSize: CGSize
    /// Frame-advance rate for looping animations (idle, sleep).
    let fps: Double
    let loops: Bool
    /// Total playback time for non-looping animations (jump, wake).
    /// Frame index is derived from elapsed-time progress, not `fps`.
    let duration: CFTimeInterval?
}

enum PetAnimation {
    static let idle = SpriteAnimationConfig(
        resourceName: "cat_idle",
        frameSize: CGSize(width: 64, height: 64),
        fps: 7,
        loops: true,
        duration: nil
    )

    static let jump = SpriteAnimationConfig(
        resourceName: "cat_jump",
        frameSize: CGSize(width: 64, height: 64),
        fps: 0,
        loops: false,
        duration: 0.9
    )

    static let sleep = SpriteAnimationConfig(
        resourceName: "cat_sleep_v2_calm",
        frameSize: CGSize(width: 64, height: 64),
        fps: 4,
        loops: true,
        duration: nil
    )

    static let wake = SpriteAnimationConfig(
        resourceName: "cat_wake",
        frameSize: CGSize(width: 64, height: 64),
        fps: 0,
        loops: false,
        duration: 0.6
    )
}

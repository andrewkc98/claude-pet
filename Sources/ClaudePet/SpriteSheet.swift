import Cocoa

struct SpriteSheet {
    let frames: [CGImage]

    init?(resourceName: String, fileExtension: String = "png", frameSize: CGSize) {
        guard let url = Bundle.main.url(forResource: resourceName, withExtension: fileExtension),
              let image = NSImage(contentsOf: url),
              let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
            return nil
        }

        let frameWidth = Int(frameSize.width)
        let frameHeight = Int(frameSize.height)
        guard frameWidth > 0,
              cgImage.height == frameHeight,
              cgImage.width % frameWidth == 0 else {
            return nil
        }

        let frameCount = cgImage.width / frameWidth
        var extracted: [CGImage] = []
        extracted.reserveCapacity(frameCount)
        for i in 0..<frameCount {
            let rect = CGRect(x: i * frameWidth, y: 0, width: frameWidth, height: frameHeight)
            guard let cropped = cgImage.cropping(to: rect) else { continue }
            extracted.append(cropped)
        }
        self.frames = extracted
    }
}

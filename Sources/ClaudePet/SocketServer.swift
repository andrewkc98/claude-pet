import Foundation
#if canImport(Darwin)
import Darwin
#endif

final class SocketServer {
    private let socketPath: String
    private let onEvent: (PetEvent) -> Void
    private let queue = DispatchQueue(label: "com.andrewtucker.ClaudePet.socketserver", qos: .utility)
    private let maxLineLength = 4096

    init(socketPath: String, onEvent: @escaping (PetEvent) -> Void) {
        self.socketPath = socketPath
        self.onEvent = onEvent
    }

    func start() {
        queue.async { [weak self] in
            self?.run()
        }
    }

    private func run() {
        let dir = (socketPath as NSString).deletingLastPathComponent
        let fm = FileManager.default
        if !fm.fileExists(atPath: dir) {
            try? fm.createDirectory(atPath: dir, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        } else {
            try? fm.setAttributes([.posixPermissions: 0o700], ofItemAtPath: dir)
        }

        unlink(socketPath)

        let fd = socket(AF_UNIX, SOCK_STREAM, 0)
        guard fd >= 0 else { return }

        var addr = sockaddr_un()
        addr.sun_family = sa_family_t(AF_UNIX)
        let pathBytes = Array(socketPath.utf8)
        guard pathBytes.count < MemoryLayout.size(ofValue: addr.sun_path) else {
            close(fd)
            return
        }
        withUnsafeMutableBytes(of: &addr.sun_path) { ptr in
            ptr.copyBytes(from: pathBytes)
        }

        let addrSize = socklen_t(MemoryLayout<sockaddr_un>.size)
        let bindResult = withUnsafePointer(to: &addr) { ptr -> Int32 in
            ptr.withMemoryRebound(to: sockaddr.self, capacity: 1) { sockPtr in
                bind(fd, sockPtr, addrSize)
            }
        }
        guard bindResult == 0 else {
            close(fd)
            return
        }

        chmod(socketPath, 0o600)

        guard listen(fd, 8) == 0 else {
            close(fd)
            return
        }

        while true {
            let clientFD = accept(fd, nil, nil)
            guard clientFD >= 0 else { continue }
            handleClient(clientFD)
        }
    }

    private func handleClient(_ fd: Int32) {
        defer { close(fd) }

        var timeout = timeval(tv_sec: 2, tv_usec: 0)
        setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, socklen_t(MemoryLayout<timeval>.size))

        var buffer = [UInt8](repeating: 0, count: 4096)
        var lineData = Data()

        while lineData.count <= maxLineLength {
            let bytesRead = read(fd, &buffer, buffer.count)
            if bytesRead <= 0 { break }
            lineData.append(contentsOf: buffer[0..<bytesRead])
        }

        for line in lineData.split(separator: UInt8(ascii: "\n")) where line.count <= maxLineLength {
            guard let event = PetEvent.decode(from: Data(line)) else { continue }
            onEvent(event)
        }
    }
}

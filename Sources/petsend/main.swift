import Foundation
#if canImport(Darwin)
import Darwin
#endif

// Fire-and-forget: connect to the pet's socket, write one JSON line, exit 0.
// Must never hang the caller (Claude Code hooks block on this), and must
// never fail loudly if the pet app isn't running.

let arguments = CommandLine.arguments
let eventType = arguments.count > 1 ? arguments[1] : "done"
let source = arguments.count > 2 ? arguments[2] : "unknown"

func jsonEscape(_ s: String) -> String {
    var result = ""
    for scalar in s.unicodeScalars {
        switch scalar {
        case "\\": result += "\\\\"
        case "\"": result += "\\\""
        case "\n": result += "\\n"
        case "\r": result += "\\r"
        case "\t": result += "\\t"
        default:
            if scalar.value < 0x20 {
                result += String(format: "\\u%04x", scalar.value)
            } else {
                result.unicodeScalars.append(scalar)
            }
        }
    }
    return result
}

/// Claude Code pipes the hook's JSON payload over stdin. We only care about
/// `transcript_path`, forwarded so the pet can check the transcript for tool
/// errors. Guarded by isatty so running `petsend` by hand from a terminal
/// (no piped stdin) never blocks waiting on input.
func readTranscriptPathFromStdin() -> String? {
    guard isatty(STDIN_FILENO) == 0 else { return nil }

    let maxBytes = 65536
    var data = Data()
    var buffer = [UInt8](repeating: 0, count: 4096)
    while data.count < maxBytes {
        let n = read(STDIN_FILENO, &buffer, buffer.count)
        if n <= 0 { break }
        data.append(contentsOf: buffer[0..<n])
    }
    guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return nil }
    return json["transcript_path"] as? String
}

func sendEvent() {
    let transcriptPath = readTranscriptPathFromStdin()

    let socketPath = NSString(string: "~/.claudepet/pet.sock").expandingTildeInPath

    let fd = socket(AF_UNIX, SOCK_STREAM, 0)
    guard fd >= 0 else { return }
    defer { close(fd) }

    var addr = sockaddr_un()
    addr.sun_family = sa_family_t(AF_UNIX)
    let pathBytes = Array(socketPath.utf8)
    guard pathBytes.count < MemoryLayout.size(ofValue: addr.sun_path) else { return }
    withUnsafeMutableBytes(of: &addr.sun_path) { ptr in
        ptr.copyBytes(from: pathBytes)
    }

    let addrSize = socklen_t(MemoryLayout<sockaddr_un>.size)
    let connectResult = withUnsafePointer(to: &addr) { ptr -> Int32 in
        ptr.withMemoryRebound(to: sockaddr.self, capacity: 1) { sockPtr in
            connect(fd, sockPtr, addrSize)
        }
    }
    guard connectResult == 0 else { return }

    let ts = Int(Date().timeIntervalSince1970)
    var json = "{\"event\":\"\(jsonEscape(eventType))\",\"source\":\"\(jsonEscape(source))\",\"ts\":\(ts)"
    if let transcriptPath {
        json += ",\"transcript_path\":\"\(jsonEscape(transcriptPath))\""
    }
    json += "}\n"

    guard let data = json.data(using: .utf8) else { return }
    _ = data.withUnsafeBytes { rawBuffer in
        write(fd, rawBuffer.baseAddress, rawBuffer.count)
    }
}

let semaphore = DispatchSemaphore(value: 0)
DispatchQueue.global(qos: .utility).async {
    sendEvent()
    semaphore.signal()
}
_ = semaphore.wait(timeout: .now() + 0.2)
exit(0)

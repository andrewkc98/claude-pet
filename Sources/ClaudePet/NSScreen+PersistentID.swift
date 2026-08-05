import Cocoa

extension NSScreen {
    /// A stable identifier for this display across launches, unlike NSScreen
    /// instances themselves which are recreated whenever displays reconfigure.
    var persistentID: String? {
        guard let screenNumber = deviceDescription[NSDeviceDescriptionKey("NSScreenNumber")] as? NSNumber else {
            return nil
        }
        let displayID = CGDirectDisplayID(screenNumber.uint32Value)
        guard let uuidRef = CGDisplayCreateUUIDFromDisplayID(displayID) else { return nil }
        let uuid = uuidRef.takeRetainedValue()
        return CFUUIDCreateString(nil, uuid) as String?
    }
}

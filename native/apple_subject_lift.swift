import AppKit
import CoreImage
import Foundation
import Vision

private struct SelectionRequest: Decodable {
    let mode: String
    let point: [Double]?
    let points: [[Double]]?
}

private enum SubjectLiftError: LocalizedError {
    case invalidArguments
    case invalidSelection(String)
    case imageLoadFailed
    case noSubjects
    case noSubjectAtSelection
    case outputFailed

    var errorDescription: String? {
        switch self {
        case .invalidArguments:
            return "Usage: apple_subject_lift <source.png> <selection.json> <output.png>"
        case .invalidSelection(let message):
            return message
        case .imageLoadFailed:
            return "The source image could not be loaded by macOS Vision."
        case .noSubjects:
            return "Apple Vision did not find a foreground subject in this image."
        case .noSubjectAtSelection:
            return "No detected subject was found at that selection. Try clicking nearer the object's center or use Smart Lasso."
        case .outputFailed:
            return "The isolated subject could not be written as a PNG."
        }
    }
}

private func clampedUnit(_ value: Double, name: String) throws -> CGFloat {
    guard value.isFinite, value >= 0.0, value <= 1.0 else {
        throw SubjectLiftError.invalidSelection("\(name) must be between 0 and 1.")
    }
    return CGFloat(value)
}

private func browserPoint(_ raw: [Double], name: String) throws -> CGPoint {
    guard raw.count == 2 else {
        throw SubjectLiftError.invalidSelection("\(name) must contain x and y.")
    }
    return CGPoint(
        x: try clampedUnit(raw[0], name: "\(name) x"),
        y: try clampedUnit(raw[1], name: "\(name) y")
    )
}

private func maskPoint(fromBrowserPoint point: CGPoint, width: Int, height: Int) -> CGPoint {
    // Browser coordinates start at the top-left. Vision normalized coordinates
    // start at the bottom-left, so flip y before projecting into the instance mask.
    let visionPoint = CGPoint(x: point.x, y: 1.0 - point.y)
    return VNImagePointForNormalizedPoint(
        visionPoint,
        max(1, width - 1),
        max(1, height - 1)
    )
}

private func labelAtPixel(
    x: Int,
    y: Int,
    baseAddress: UnsafeMutableRawPointer,
    bytesPerRow: Int,
    width: Int,
    height: Int
) -> UInt8 {
    guard x >= 0, x < width, y >= 0, y < height else { return 0 }
    return baseAddress.load(fromByteOffset: y * bytesPerRow + x, as: UInt8.self)
}

private func selectedLabelForClick(_ browserSelection: CGPoint, observation: VNInstanceMaskObservation) throws -> Int {
    let mask = observation.instanceMask
    let width = CVPixelBufferGetWidth(mask)
    let height = CVPixelBufferGetHeight(mask)
    let projected = maskPoint(fromBrowserPoint: browserSelection, width: width, height: height)
    let centerX = Int(projected.x.rounded())
    let centerY = Int(projected.y.rounded())

    CVPixelBufferLockBaseAddress(mask, .readOnly)
    defer { CVPixelBufferUnlockBaseAddress(mask, .readOnly) }
    guard let baseAddress = CVPixelBufferGetBaseAddress(mask) else {
        throw SubjectLiftError.noSubjectAtSelection
    }
    let bytesPerRow = CVPixelBufferGetBytesPerRow(mask)

    let direct = labelAtPixel(
        x: centerX,
        y: centerY,
        baseAddress: baseAddress,
        bytesPerRow: bytesPerRow,
        width: width,
        height: height
    )
    if direct != 0, observation.allInstances.contains(Int(direct)) {
        return Int(direct)
    }

    // A click can land on a one-pixel hole, branch edge, hair gap, or antialiased
    // boundary. Search a small neighborhood and choose the nearest detected label.
    let maxRadius = max(4, min(24, min(width, height) / 18))
    var bestLabel = 0
    var bestDistance = Int.max

    for radius in 1...maxRadius {
        for dy in -radius...radius {
            for dx in -radius...radius where abs(dx) == radius || abs(dy) == radius {
                let label = labelAtPixel(
                    x: centerX + dx,
                    y: centerY + dy,
                    baseAddress: baseAddress,
                    bytesPerRow: bytesPerRow,
                    width: width,
                    height: height
                )
                guard label != 0, observation.allInstances.contains(Int(label)) else { continue }
                let distance = dx * dx + dy * dy
                if distance < bestDistance {
                    bestDistance = distance
                    bestLabel = Int(label)
                }
            }
        }
        if bestLabel != 0 { break }
    }

    guard bestLabel != 0 else { throw SubjectLiftError.noSubjectAtSelection }
    return bestLabel
}

private func pointInPolygon(_ point: CGPoint, polygon: [CGPoint]) -> Bool {
    guard polygon.count >= 3 else { return false }
    var inside = false
    var previous = polygon[polygon.count - 1]

    for current in polygon {
        let spansY = (current.y > point.y) != (previous.y > point.y)
        if spansY {
            let denominator = previous.y - current.y
            if abs(denominator) > 0.000001 {
                let crossingX = (previous.x - current.x) * (point.y - current.y) / denominator + current.x
                if point.x < crossingX { inside.toggle() }
            }
        }
        previous = current
    }
    return inside
}

private func selectedLabelForLasso(_ rawPoints: [[Double]], observation: VNInstanceMaskObservation) throws -> Int {
    guard rawPoints.count >= 3 else {
        throw SubjectLiftError.invalidSelection("Draw a lasso around the object first.")
    }
    guard rawPoints.count <= 800 else {
        throw SubjectLiftError.invalidSelection("The lasso contains too many points. Draw a simpler loop around the object.")
    }

    let mask = observation.instanceMask
    let width = CVPixelBufferGetWidth(mask)
    let height = CVPixelBufferGetHeight(mask)
    let polygon = try rawPoints.enumerated().map { index, raw in
        maskPoint(
            fromBrowserPoint: try browserPoint(raw, name: "lasso point \(index + 1)"),
            width: width,
            height: height
        )
    }

    let minX = max(0, Int(floor(polygon.map(\.x).min() ?? 0)))
    let maxX = min(width - 1, Int(ceil(polygon.map(\.x).max() ?? CGFloat(width - 1))))
    let minY = max(0, Int(floor(polygon.map(\.y).min() ?? 0)))
    let maxY = min(height - 1, Int(ceil(polygon.map(\.y).max() ?? CGFloat(height - 1))))
    guard minX <= maxX, minY <= maxY else { throw SubjectLiftError.noSubjectAtSelection }

    CVPixelBufferLockBaseAddress(mask, .readOnly)
    defer { CVPixelBufferUnlockBaseAddress(mask, .readOnly) }
    guard let baseAddress = CVPixelBufferGetBaseAddress(mask) else {
        throw SubjectLiftError.noSubjectAtSelection
    }
    let bytesPerRow = CVPixelBufferGetBytesPerRow(mask)

    var counts: [Int: Int] = [:]
    // Instance masks are small (typically 512x512), so sampling every pixel in the
    // lasso is inexpensive and makes a rough lasso tolerant of background inside it.
    for y in minY...maxY {
        for x in minX...maxX {
            guard pointInPolygon(CGPoint(x: CGFloat(x) + 0.5, y: CGFloat(y) + 0.5), polygon: polygon) else {
                continue
            }
            let label = Int(labelAtPixel(
                x: x,
                y: y,
                baseAddress: baseAddress,
                bytesPerRow: bytesPerRow,
                width: width,
                height: height
            ))
            guard label != 0, observation.allInstances.contains(label) else { continue }
            counts[label, default: 0] += 1
        }
    }

    guard let best = counts.max(by: { lhs, rhs in
        if lhs.value == rhs.value { return lhs.key > rhs.key }
        return lhs.value < rhs.value
    })?.key else {
        throw SubjectLiftError.noSubjectAtSelection
    }
    return best
}

@available(macOS 14.0, *)
private func runSubjectLift(sourceURL: URL, selectionURL: URL, outputURL: URL) throws {
    let selectionData = try Data(contentsOf: selectionURL)
    let selection = try JSONDecoder().decode(SelectionRequest.self, from: selectionData)

    guard let sourceImage = CIImage(contentsOf: sourceURL) else {
        throw SubjectLiftError.imageLoadFailed
    }

    let request = VNGenerateForegroundInstanceMaskRequest()
    let handler = VNImageRequestHandler(ciImage: sourceImage, options: [:])
    try handler.perform([request])

    guard let observation = request.results?.first, !observation.allInstances.isEmpty else {
        throw SubjectLiftError.noSubjects
    }

    let label: Int
    switch selection.mode {
    case "click":
        guard let rawPoint = selection.point else {
            throw SubjectLiftError.invalidSelection("Click the object you want to isolate first.")
        }
        label = try selectedLabelForClick(
            browserPoint(rawPoint, name: "selection point"),
            observation: observation
        )
    case "lasso":
        guard let rawPoints = selection.points else {
            throw SubjectLiftError.invalidSelection("Draw a lasso around the object first.")
        }
        label = try selectedLabelForLasso(rawPoints, observation: observation)
    default:
        throw SubjectLiftError.invalidSelection("Unknown smart subject selection mode.")
    }

    let selectedInstances = IndexSet(integer: label)
    let maskedBuffer = try observation.generateMaskedImage(
        ofInstances: selectedInstances,
        from: handler,
        croppedToInstancesExtent: false
    )

    let maskedImage = CIImage(cvPixelBuffer: maskedBuffer)
    let context = CIContext(options: nil)
    guard let cgImage = context.createCGImage(maskedImage, from: maskedImage.extent) else {
        throw SubjectLiftError.outputFailed
    }
    let bitmap = NSBitmapImageRep(cgImage: cgImage)
    guard let pngData = bitmap.representation(using: .png, properties: [:]) else {
        throw SubjectLiftError.outputFailed
    }
    try pngData.write(to: outputURL, options: .atomic)

    let metadata = ["instance": label]
    if let data = try? JSONSerialization.data(withJSONObject: metadata),
       let text = String(data: data, encoding: .utf8) {
        print(text)
    }
}

private func main() throws {
    let arguments = CommandLine.arguments
    guard arguments.count == 4 else { throw SubjectLiftError.invalidArguments }

    guard #available(macOS 14.0, *) else {
        throw SubjectLiftError.invalidSelection(
            "Smart subject isolation requires macOS 14 or newer because it uses Apple's local Vision framework."
        )
    }

    try runSubjectLift(
        sourceURL: URL(fileURLWithPath: arguments[1]),
        selectionURL: URL(fileURLWithPath: arguments[2]),
        outputURL: URL(fileURLWithPath: arguments[3])
    )
}

do {
    try main()
} catch {
    let message = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
    FileHandle.standardError.write(Data((message + "\n").utf8))
    exit(1)
}

import DesignLaneCore
import Foundation

public struct OpalAPIClient: Sendable {
    public enum ClientError: Error, CustomStringConvertible {
        case invalidURL
        case httpStatus(Int)
        case invalidResponse

        public var description: String {
            switch self {
            case .invalidURL:
                return "Invalid URL"
            case .httpStatus(let code):
                return "HTTP status \(code)"
            case .invalidResponse:
                return "Invalid response"
            }
        }
    }

    public let baseURL: URL
    private let session: URLSession
    private let decoder: JSONDecoder

    public init(baseURL: URL, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.session = session
        self.decoder = JSONDecoder()
    }

    public func getHealth() async throws -> HealthResponse {
        try await getJSON(path: "/api/health", as: HealthResponse.self)
    }

    public func getStatus() async throws -> StatusResponse {
        try await getJSON(path: "/api/status", as: StatusResponse.self)
    }

    public func getTelemetryLatest() async throws -> JSONValue {
        try await getJSON(path: "/api/telemetry/latest", as: JSONValue.self)
    }

    public func getTelemetryHealth() async throws -> JSONValue {
        try await getJSON(path: "/api/telemetry/health", as: JSONValue.self)
    }

    public func getTelemetrySummary() async throws -> JSONValue {
        try await getJSON(path: "/api/telemetry/summary", as: JSONValue.self)
    }

    public func getBudget() async throws -> JSONValue {
        try await getJSON(path: "/api/budget", as: JSONValue.self)
    }

    public func getTelemetryLog() async throws -> JSONValue {
        try await getJSON(path: "/api/telemetry/log", as: JSONValue.self)
    }


    public func getRoot() async throws -> JSONValue {
        try await getJSON(path: "/", as: JSONValue.self)
    }

    public func createJob(prompt: String, fileURL: URL, metadata: [String: JSONValue]? = nil) async throws -> JobInfo {
        let url = try urlFor(path: "/api/jobs")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"

        let boundary = "Boundary-\(UUID().uuidString)"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        var body = Data()

        // Prompt
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"prompt\"\r\n\r\n".data(using: .utf8)!)
        body.append("\(prompt)\r\n".data(using: .utf8)!)

        // Metadata (Optional)
        if let metadata = metadata {
            let metaData = try JSONEncoder().encode(metadata)
            body.append("--\(boundary)\r\n".data(using: .utf8)!)
            body.append("Content-Disposition: form-data; name=\"metadata\"\r\n\r\n".data(using: .utf8)!)
            body.append(metaData)
            body.append("\r\n".data(using: .utf8)!)
        }

        // File
        let fileName = fileURL.lastPathComponent
        let fileData = try Data(contentsOf: fileURL)
        let mimeType = mimeType(for: fileURL.pathExtension)
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"file\"; filename=\"\(fileName)\"\r\n".data(using: .utf8)!)
        body.append("Content-Type: \(mimeType)\r\n\r\n".data(using: .utf8)!)
        body.append(fileData)
        body.append("\r\n".data(using: .utf8)!)

        body.append("--\(boundary)--\r\n".data(using: .utf8)!)

        request.httpBody = body

        let (data, response) = try await session.data(for: request)

        guard let http = response as? HTTPURLResponse else {
            throw ClientError.invalidResponse
        }
        guard (200...299).contains(http.statusCode) else {
            throw ClientError.httpStatus(http.statusCode)
        }

        return try decoder.decode(JobInfo.self, from: data)
    }

    public func getJob(id: String) async throws -> JobDetail {
        try await getJSON(path: "/api/jobs/\(id)", as: JobDetail.self)
    }

    private func mimeType(for pathExtension: String) -> String {
        switch pathExtension.lowercased() {
        case "obj": return "application/x-tgif"
        case "zip": return "application/zip"
        case "pdf": return "application/pdf"
        case "dwg": return "image/vnd.dwg"
        default: return "application/octet-stream"
        }
    }

    private func getJSON<T: Decodable>(path: String, as: T.Type) async throws -> T {
        let url = try urlFor(path: path)
        var request = URLRequest(url: url)
        request.httpMethod = "GET"

        let (data, response) = try await session.data(for: request)

        guard let http = response as? HTTPURLResponse else {
            throw ClientError.invalidResponse
        }
        guard (200...299).contains(http.statusCode) else {
            throw ClientError.httpStatus(http.statusCode)
        }

        return try decoder.decode(T.self, from: data)
    }

    private func urlFor(path: String) throws -> URL {
        var components = URLComponents(url: baseURL, resolvingAgainstBaseURL: false)
        guard components != nil else { throw ClientError.invalidURL }

        let basePath = (components?.path ?? "").trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        let appendPath = path.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        let mergedPath: String
        if basePath.isEmpty {
            mergedPath = "/" + appendPath
        } else if appendPath.isEmpty {
            mergedPath = "/" + basePath
        } else {
            mergedPath = "/" + basePath + "/" + appendPath
        }

        components?.path = mergedPath

        guard let url = components?.url else {
            throw ClientError.invalidURL
        }
        return url
    }
}

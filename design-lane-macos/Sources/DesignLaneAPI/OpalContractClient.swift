import DesignLaneCore
import Foundation

public struct OpenAPIContractSummary: Sendable, Equatable {
    public var openapi: String?
    public var title: String?
    public var version: String?
    public var description: String?
    public var paths: [String]

    public init(openapi: String?, title: String?, version: String?, description: String?, paths: [String]) {
        self.openapi = openapi
        self.title = title
        self.version = version
        self.description = description
        self.paths = paths
    }
}

public struct OpalContractClient: Sendable {
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

    public func getContractSummary() async throws -> OpenAPIContractSummary {
        let raw = try await getJSON(path: "/openapi.json", as: JSONValue.self)
        return OpenAPIContractSummary.fromOpenAPIJSON(raw)
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

private extension OpenAPIContractSummary {
    static func fromOpenAPIJSON(_ json: JSONValue) -> OpenAPIContractSummary {
        guard case .object(let root) = json else {
            return OpenAPIContractSummary(openapi: nil, title: nil, version: nil, description: nil, paths: [])
        }

        let openapi = root["openapi"]?.stringValue

        var title: String?
        var version: String?
        var description: String?
        if case .object(let info)? = root["info"] {
            title = info["title"]?.stringValue
            version = info["version"]?.stringValue
            description = info["description"]?.stringValue
        }

        var paths: [String] = []
        if case .object(let pathsObject)? = root["paths"] {
            paths = pathsObject.keys.sorted()
        }

        return OpenAPIContractSummary(
            openapi: openapi,
            title: title,
            version: version,
            description: description,
            paths: paths
        )
    }
}

private extension JSONValue {
    var stringValue: String? {
        if case .string(let s) = self { return s }
        return nil
    }
}

import Foundation

enum AppBaseURL {
    static let environmentVariableName = "OPAL_BASE_URL"

    static func resolve(storedValue: String) -> URL? {
        if let envValue = ProcessInfo.processInfo.environment[environmentVariableName],
           let envURL = parseBaseURL(envValue) {
            return envURL
        }

        return parseBaseURL(storedValue)
    }

    static func parseBaseURL(_ raw: String) -> URL? {
        let trimmed = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return nil }

        guard let url = URL(string: trimmed),
              let scheme = url.scheme?.lowercased(),
              scheme == "http" || scheme == "https",
              url.host != nil
        else {
            return nil
        }

        return url
    }
}

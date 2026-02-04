import Foundation

public struct HealthResponse: Codable, Sendable, Equatable {
    public let status: String
    public let timestamp: String
    public let service: String?
    public let version: String?

    public init(status: String, timestamp: String, service: String?, version: String?) {
        self.status = status
        self.timestamp = timestamp
        self.service = service
        self.version = version
    }
}

public struct StatusResponse: Codable, Sendable, Equatable {
    public let status: String
    public let uptime: String?
    public let port: Int?

    public init(status: String, uptime: String?, port: Int?) {
        self.status = status
        self.uptime = uptime
        self.port = port
    }
}

public enum JobStatus: String, Codable, Sendable, CaseIterable {
    case queued
    case running
    case succeeded
    case failed

    public var isTerminal: Bool {
        switch self {
        case .succeeded, .failed:
            return true
        case .queued, .running:
            return false
        }
    }
}

public struct JobInfo: Codable, Sendable, Equatable {
    public let id: String
    public let status: JobStatus

    public init(id: String, status: JobStatus) {
        self.id = id
        self.status = status
    }
}

public struct JobOutput: Codable, Sendable, Equatable {
    public let path: String
    public let kind: String // model, image, log, artifact

    public init(path: String, kind: String) {
        self.path = path
        self.kind = kind
    }
}

public struct JobError: Codable, Sendable, Equatable {
    public let message: String

    public init(message: String) {
        self.message = message
    }
}

public struct JobDetail: Codable, Sendable, Equatable {
    public let id: String
    public let status: JobStatus
    public let outputs: [JobOutput]?
    public let error: JobError?

    public init(id: String, status: JobStatus, outputs: [JobOutput]?, error: JobError?) {
        self.id = id
        self.status = status
        self.outputs = outputs
        self.error = error
    }
}

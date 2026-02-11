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
    public let id: String
    public let name: String
    public let kind: String
    public let mime: String
    public let sha256: String
    public let href: String

    public init(id: String, name: String, kind: String, mime: String, sha256: String, href: String) {
        self.id = id
        self.name = name
        self.kind = kind
        self.mime = mime
        self.sha256 = sha256
        self.href = href
    }
}

public struct JobError: Codable, Sendable, Equatable {
    public let message: String

    public init(message: String) {
        self.message = message
    }
}

public struct RunProvenance: Codable, Sendable, Equatable {
    public let engine: String
    public let version: String?
    public let inputChecksum: String?

    public init(engine: String, version: String?, inputChecksum: String?) {
        self.engine = engine
        self.version = version
        self.inputChecksum = inputChecksum
    }

    enum CodingKeys: String, CodingKey {
        case engine
        case version
        case inputChecksum = "input_checksum"
    }
}

public struct JobDetail: Codable, Sendable, Equatable {
    public let id: String
    public let status: JobStatus
    public let outputs: [JobOutput]?
    public let error: JobError?
    public let runProvenance: RunProvenance?
    public let createdAt: String?
    public let startedAt: String?
    public let completedAt: String?

    public init(id: String, status: JobStatus, outputs: [JobOutput]?, error: JobError?, runProvenance: RunProvenance?, createdAt: String?, startedAt: String?, completedAt: String?) {
        self.id = id
        self.status = status
        self.outputs = outputs
        self.error = error
        self.runProvenance = runProvenance
        self.createdAt = createdAt
        self.startedAt = startedAt
        self.completedAt = completedAt
    }

    enum CodingKeys: String, CodingKey {
        case id
        case status
        case outputs
        case error
        case runProvenance = "run_provenance"
        case createdAt = "created_at"
        case startedAt = "started_at"
        case completedAt = "completed_at"
    }
}

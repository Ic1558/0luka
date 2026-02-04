import DesignLaneAPI
import DesignLaneCore
import Foundation

@MainActor
final class DashboardViewModel: ObservableObject {
    @Published private(set) var health: HealthResponse?
    @Published private(set) var status: StatusResponse?

    @Published private(set) var telemetryLatest: JSONValue?
    @Published private(set) var telemetryHealth: JSONValue?
    @Published private(set) var telemetrySummary: JSONValue?
    @Published private(set) var budget: JSONValue?
    @Published private(set) var telemetryLog: JSONValue?
    @Published private(set) var root: JSONValue?

    @Published private(set) var lastErrorMessage: String?

    private var client: OpalAPIClient?
    private var didInitialRefresh = false
    private var didInitialTelemetryRefresh = false

    var healthLines: [String] {
        guard let health else {
            return ["status: -", "timestamp: -"]
        }
        var lines: [String] = [
            "status: \(health.status)",
            "timestamp: \(health.timestamp)"
        ]
        if let service = health.service { lines.append("service: \(service)") }
        if let version = health.version { lines.append("version: \(version)") }
        return lines
    }

    var statusLines: [String] {
        guard let status else {
            return ["status: -", "uptime: -", "port: -"]
        }
        return [
            "status: \(status.status)",
            "uptime: \(status.uptime ?? "-")",
            "port: \(status.port.map(String.init) ?? "-")"
        ]
    }

    func setClient(baseURL: URL) {
        client = OpalAPIClient(baseURL: baseURL)
        didInitialRefresh = false
        didInitialTelemetryRefresh = false
    }

    func refreshIfNeeded() async {
        guard !didInitialRefresh else { return }
        didInitialRefresh = true
        await refresh()
    }

    func refreshTelemetryIfNeeded() async {
        guard !didInitialTelemetryRefresh else { return }
        didInitialTelemetryRefresh = true
        await refreshTelemetryOnly()
    }

    func refresh() async {
        lastErrorMessage = nil
        guard let client else {
            lastErrorMessage = "Client not configured"
            return
        }

        do {
            async let healthTask = client.getHealth()
            async let statusTask = client.getStatus()

            health = try await healthTask
            status = try await statusTask
        } catch {
            lastErrorMessage = String(describing: error)
        }
    }

    func refreshTelemetryOnly() async {
        lastErrorMessage = nil
        guard let client else {
            lastErrorMessage = "Client not configured"
            return
        }

        do {
            async let latestTask = client.getTelemetryLatest()
            async let healthTask = client.getTelemetryHealth()
            async let summaryTask = client.getTelemetrySummary()
            async let budgetTask = client.getBudget()
            async let logTask = client.getTelemetryLog()
            async let rootTask = client.getRoot()

            telemetryLatest = try await latestTask
            telemetryHealth = try await healthTask
            telemetrySummary = try await summaryTask
            budget = try await budgetTask
            telemetryLog = try await logTask
            root = try await rootTask
        } catch {
            lastErrorMessage = String(describing: error)
        }
    }
}

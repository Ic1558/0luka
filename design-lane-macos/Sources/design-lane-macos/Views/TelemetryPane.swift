import SwiftUI

struct TelemetryPane: View {
    let baseURL: URL
    @ObservedObject var model: DashboardViewModel

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                HStack {
                    Text("Telemetry")
                        .font(.system(size: 26, weight: .semibold))
                    Spacer()
                    Button("Refresh") {
                        Task { await model.refreshTelemetryOnly() }
                    }
                }

                JSONViewer(title: "Summary (/api/telemetry/summary)", value: model.telemetrySummary)
                JSONViewer(title: "Latest (/api/telemetry/latest)", value: model.telemetryLatest)
                JSONViewer(title: "Health (/api/telemetry/health)", value: model.telemetryHealth)
                JSONViewer(title: "Budget (/api/budget)", value: model.budget)
                JSONViewer(title: "Log (/api/telemetry/log)", value: model.telemetryLog)
                JSONViewer(title: "Root (/)", value: model.root)
            }
            .padding(18)
        }
        .task {
            await model.refreshTelemetryIfNeeded()
        }
    }
}

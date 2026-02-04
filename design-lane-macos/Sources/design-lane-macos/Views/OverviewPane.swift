import DesignLaneCore
import SwiftUI

struct OverviewPane: View {
    let baseURL: URL
    @Binding var storedBaseURLString: String
    @ObservedObject var model: DashboardViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .firstTextBaseline) {
                Text("OPAL")
                    .font(.system(size: 26, weight: .semibold))
                Spacer()
                Button("Refresh") {
                    Task { await model.refresh() }
                }
            }

            VStack(alignment: .leading, spacing: 6) {
                Text("Base URL")
                    .font(.headline)

                HStack(spacing: 10) {
                    Text(baseURL.absoluteString)
                        .font(.system(.body, design: .monospaced))
                        .textSelection(.enabled)

                    Spacer()

                    Button("Edit") {
                        storedBaseURLString = ""
                    }
                }
                .foregroundStyle(.secondary)

                if ProcessInfo.processInfo.environment[AppBaseURL.environmentVariableName] != nil {
                    Text("Using OPAL_BASE_URL environment override")
                        .font(.callout)
                        .foregroundStyle(.secondary)
                }
            }

            HStack(spacing: 18) {
                StatusCard(title: "Health", lines: model.healthLines)
                StatusCard(title: "Status", lines: model.statusLines)
            }

            if let error = model.lastErrorMessage {
                Text(error)
                    .foregroundStyle(.red)
                    .font(.callout)
            }

            Spacer()
        }
        .padding(18)
        .task {
            await model.refreshIfNeeded()
        }
    }
}

private struct StatusCard: View {
    let title: String
    let lines: [String]

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.headline)
            ForEach(lines, id: \.self) { line in
                Text(line)
                    .font(.system(.body, design: .monospaced))
                    .foregroundStyle(.secondary)
                    .textSelection(.enabled)
            }
            Spacer(minLength: 0)
        }
        .padding(12)
        .frame(maxWidth: .infinity, minHeight: 120, alignment: .topLeading)
        .background(Color(nsColor: .windowBackgroundColor).opacity(0.65))
        .overlay(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .stroke(Color(nsColor: .separatorColor), lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
    }
}

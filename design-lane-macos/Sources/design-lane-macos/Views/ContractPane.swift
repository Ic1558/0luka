import SwiftUI

struct ContractPane: View {
    let baseURL: URL
    @ObservedObject var model: ContractViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Text("API Contract")
                    .font(.system(size: 26, weight: .semibold))
                Spacer()
                Button("Fetch") {
                    Task { await model.fetch() }
                }
            }

            if let summary = model.summary {
                VStack(alignment: .leading, spacing: 6) {
                    Text("Title: \(summary.title ?? "-")")
                    Text("Version: \(summary.version ?? "-")")
                    if let openapi = summary.openapi {
                        Text("OpenAPI: \(openapi)")
                    }
                    Text("Paths: \(summary.paths.count)")
                }
                .foregroundStyle(.secondary)
                .textSelection(.enabled)

                ScrollView {
                    VStack(alignment: .leading, spacing: 4) {
                        ForEach(summary.paths, id: \.self) { p in
                            Text(p)
                                .font(.system(.body, design: .monospaced))
                                .foregroundStyle(.secondary)
                                .textSelection(.enabled)
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
            } else {
                Text("Fetch /openapi.json from \(baseURL.absoluteString) to confirm the live contract.")
                    .foregroundStyle(.secondary)
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
            await model.fetchIfNeeded()
        }
    }
}

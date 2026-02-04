import DesignLaneAPI
import DesignLaneCore
import SwiftUI

struct ContentView: View {
    @AppStorage("opal.base_url") private var baseURLString: String = ""

    var body: some View {
        let resolvedURL = AppBaseURL.resolve(storedValue: baseURLString)

        Group {
            if let baseURL = resolvedURL {
                DashboardView(baseURL: baseURL, storedBaseURLString: $baseURLString)
            } else {
                BaseURLSetupView(storedBaseURLString: $baseURLString)
            }
        }
        .frame(minWidth: 920, minHeight: 620)
    }
}

private struct DashboardView: View {
    let baseURL: URL
    @Binding var storedBaseURLString: String

    @StateObject private var dashboard = DashboardViewModel()
    @StateObject private var contract = ContractViewModel()
    @StateObject private var job = JobViewModel()

    var body: some View {
        TabView {
            OverviewPane(
                baseURL: baseURL,
                storedBaseURLString: $storedBaseURLString,
                model: dashboard
            )
            .tabItem { 
                Label("Overview", systemImage: "gauge")
            }

            JobPane(model: job)
                .tabItem {
                    Label("Run Job", systemImage: "play.circle")
                }

            TelemetryPane(
                baseURL: baseURL,
                model: dashboard
            )
            .tabItem {
                Label("Telemetry", systemImage: "chart.bar")
            }

            ContractPane(
                baseURL: baseURL,
                model: contract
            )
            .tabItem {
                Label("Contract", systemImage: "doc.text")
            }
        }
        .onChange(of: baseURL) { newValue in
            dashboard.setClient(baseURL: newValue)
            contract.setClient(baseURL: newValue)
            job.setClient(baseURL: newValue)
        }
        .onAppear {
            dashboard.setClient(baseURL: baseURL)
            contract.setClient(baseURL: baseURL)
            job.setClient(baseURL: baseURL)
        }
    }
}

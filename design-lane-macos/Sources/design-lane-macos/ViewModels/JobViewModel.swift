import DesignLaneAPI
import DesignLaneCore
import Foundation
import Combine

@MainActor
final class JobViewModel: ObservableObject {
    enum ViewState: Equatable {
        case idle
        case submitting
        case processing(id: String, status: JobStatus)
        case result(JobDetail)
        case error(String)
    }

    @Published private(set) var viewState: ViewState = .idle
    @Published var prompt: String = ""
    @Published var selectedFileURL: URL?
    @Published var selectedEngine: String = "nano_banana_engine" // Default Real Engine
    @Published var lastJobDetail: JobDetail?

    private var client: OpalAPIClient?
    private var pollTask: Task<Void, Never>?

    let availableEngines = ["nano_banana_engine", "mock_engine_v1"]

    func setClient(baseURL: URL) {
        client = OpalAPIClient(baseURL: baseURL)
    }

    func submitJob() async {
        guard let client else {
            viewState = .error("Client not configured")
            return
        }
        guard !prompt.isEmpty else {
            viewState = .error("Prompt cannot be empty")
            return
        }
        guard let fileURL = selectedFileURL else {
            viewState = .error("Please select a file to process")
            return
        }

        viewState = .submitting

        do {
            // Inject engine selection into metadata
            let metadata: [String: JSONValue] = [
                "engine": .string(selectedEngine)
            ]
            
            let info = try await client.createJob(prompt: prompt, fileURL: fileURL, metadata: metadata)
            viewState = .processing(id: info.id, status: info.status)
            startPolling(jobID: info.id)
        } catch {
            viewState = .error("Failed to submit: \(error.localizedDescription)")
        }
    }

    private func startPolling(jobID: String) {
        pollTask?.cancel()
        pollTask = Task {
            while !Task.isCancelled {
                do {
                    try await Task.sleep(nanoseconds: 2 * 1_000_000_000) // 2s
                    guard let detail = try await client?.getJob(id: jobID) else { break }
                    
                    self.lastJobDetail = detail
                    
                    if detail.status.isTerminal {
                        self.viewState = .result(detail)
                        break
                    } else {
                        self.viewState = .processing(id: jobID, status: detail.status)
                    }
                } catch {
                    // Log error but continue polling unless it's a 404/terminal error
                    print("Polling error: \(error)")
                }
            }
        }
    }

    func reset() {
        pollTask?.cancel()
        pollTask = nil
        viewState = .idle
        prompt = ""
        selectedFileURL = nil
        lastJobDetail = nil
    }

    deinit {
        pollTask?.cancel()
    }
}

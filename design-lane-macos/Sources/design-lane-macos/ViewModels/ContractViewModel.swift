import DesignLaneAPI
import Foundation

@MainActor
final class ContractViewModel: ObservableObject {
    @Published private(set) var summary: OpenAPIContractSummary?
    @Published private(set) var lastErrorMessage: String?

    private var client: OpalContractClient?
    private var didInitialFetch = false

    func setClient(baseURL: URL) {
        client = OpalContractClient(baseURL: baseURL)
        didInitialFetch = false
    }

    func fetchIfNeeded() async {
        guard !didInitialFetch else { return }
        didInitialFetch = true
        await fetch()
    }

    func fetch() async {
        lastErrorMessage = nil
        guard let client else {
            lastErrorMessage = "Client not configured"
            return
        }

        do {
            summary = try await client.getContractSummary()
        } catch {
            lastErrorMessage = String(describing: error)
        }
    }
}

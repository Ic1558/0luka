import XCTest
@testable import DesignLaneCore

final class DesignLaneCoreTests: XCTestCase {
    func testJobDetailDecoding() throws {
        let json = """
        {
            "id": "job_123",
            "status": "succeeded",
            "outputs": [
                {
                    "id": "art_1",
                    "name": "result.obj",
                    "kind": "model",
                    "mime": "model/obj",
                    "sha256": "hash123",
                    "href": "/api/artifacts/job_123/result.obj"
                }
            ],
            "error": null
        }
        """.data(using: .utf8)!

        let decoder = JSONDecoder()
        let detail = try decoder.decode(JobDetail.self, from: json)

        XCTAssertEqual(detail.id, "job_123")
        XCTAssertEqual(detail.status, .succeeded)
        XCTAssertEqual(detail.outputs?.first?.name, "result.obj")
        XCTAssertEqual(detail.outputs?.first?.kind, "model")
        XCTAssertEqual(detail.outputs?.first?.href, "/api/artifacts/job_123/result.obj")
    }
}

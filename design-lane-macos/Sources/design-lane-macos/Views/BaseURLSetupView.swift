import SwiftUI

struct BaseURLSetupView: View {
    @Binding var storedBaseURLString: String
    @State private var draft: String = ""
    @State private var errorMessage: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Design Lane")
                .font(.system(size: 30, weight: .semibold))

            Text("Enter the OPAL API base URL (LAN / Tailscale / WAN).")
                .foregroundStyle(.secondary)

            HStack(spacing: 10) {
                TextField("https://host:7001", text: $draft)
                    .textFieldStyle(.roundedBorder)
                    .frame(width: 420)

                Button("Save") {
                    save()
                }
                .keyboardShortcut(.defaultAction)
            }

            if let errorMessage {
                Text(errorMessage)
                    .foregroundStyle(.red)
                    .font(.callout)
            }

            VStack(alignment: .leading, spacing: 6) {
                Text("Notes")
                    .font(.headline)
                Text("- The app never hardcodes a server address.")
                Text("- You can override with the environment variable OPAL_BASE_URL.")
            }
            .font(.callout)
            .foregroundStyle(.secondary)

            Spacer()
        }
        .padding(24)
        .onAppear {
            draft = storedBaseURLString
        }
    }

    private func save() {
        guard AppBaseURL.parseBaseURL(draft) != nil else {
            errorMessage = "Invalid URL. Use http(s)://host[:port]"
            return
        }
        storedBaseURLString = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        errorMessage = nil
    }
}

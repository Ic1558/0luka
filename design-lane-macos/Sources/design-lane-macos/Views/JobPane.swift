import DesignLaneAPI
import DesignLaneCore
import SwiftUI
import UniformTypeIdentifiers

struct JobPane: View {
    @ObservedObject var model: JobViewModel
    @State private var showingFilePicker = false

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack {
                Text("Design Lane Pipeline")
                    .font(.system(size: 26, weight: .semibold))
                Spacer()
                if model.viewState != .idle {
                    Button("Reset") {
                        model.reset()
                    }
                }
            }

            Divider()

            switch model.viewState {
            case .idle:
                JobInputForm(model: model, showingFilePicker: $showingFilePicker)
            case .submitting:
                VStack(spacing: 20) {
                    ProgressView()
                    Text("Submitting to Kernel...")
                        .font(.headline)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            case .processing(let id, let status):
                JobProgressView(model: model, id: id, status: status)
            case .result(let detail):
                JobResultView(model: model, detail: detail)
            case .error(let message):
                VStack(spacing: 20) {
                    Image(systemName: "exclamationmark.triangle")
                        .font(.system(size: 48))
                        .foregroundStyle(.red)
                    Text(message)
                        .multilineTextAlignment(.center)
                        .foregroundStyle(.secondary)
                    Button("Try Again") {
                        model.reset()
                    }
                    .keyboardShortcut(.defaultAction)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .padding(18)
        .fileImporter(
            isPresented: $showingFilePicker,
            allowedContentTypes: [.item],
            allowsMultipleSelection: false
        ) { result in
            switch result {
            case .success(let urls):
                model.selectedFileURL = urls.first
            case .failure(let error):
                print("File selection failed: \(error)")
            }
        }
    }
}

private struct JobInputForm: View {
    @ObservedObject var model: JobViewModel
    @Binding var showingFilePicker: Bool

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                VStack(alignment: .leading, spacing: 8) {
                    Text("1. Processing Instructions")
                        .font(.headline)
                    TextEditor(text: $model.prompt)
                        .frame(height: 100)
                        .padding(4)
                        .background(Color(nsColor: .windowBackgroundColor))
                        .overlay(
                            RoundedRectangle(cornerRadius: 6)
                                .stroke(Color(nsColor: .separatorColor), lineWidth: 1)
                        )
                }

                VStack(alignment: .leading, spacing: 8) {
                    Text("2. Target Artifact")
                        .font(.headline)
                    
                    HStack {
                        if let fileURL = model.selectedFileURL {
                            Image(systemName: "doc.fill")
                            Text(fileURL.lastPathComponent)
                                .font(.system(.body, design: .monospaced))
                        } else {
                            Text("No file selected")
                                .foregroundStyle(.secondary)
                        }
                        
                        Spacer()
                        
                        Button(model.selectedFileURL == nil ? "Select File..." : "Change...") {
                            showingFilePicker = true
                        }
                    }
                    .padding(10)
                    .background(Color(nsColor: .windowBackgroundColor).opacity(0.5))
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                }

                Spacer()

                Button {
                    Task { await model.submitJob() }
                } label: {
                    Text("Run Pipeline")
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 8)
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
                .disabled(model.prompt.isEmpty || model.selectedFileURL == nil)
            }
        }
    }
}

private struct JobProgressView: View {
    @ObservedObject var model: JobViewModel
    let id: String
    let status: JobStatus

    var body: some View {
        VStack(spacing: 30) {
            VStack(spacing: 12) {
                ProgressView()
                    .scaleEffect(1.5)
                
                Text(status == .queued ? "Waiting in Queue..." : "Heavy Computation in Progress...")
                    .font(.title3)
                    .fontWeight(.medium)
            }

            VStack(alignment: .leading, spacing: 10) {
                LabeledContent("Job ID", value: id)
                LabeledContent("Status", value: status.rawValue.uppercased())
                    .foregroundStyle(status == .running ? .blue : .secondary)
            }
            .padding()
            .background(Color(nsColor: .windowBackgroundColor).opacity(0.5))
            .clipShape(RoundedRectangle(cornerRadius: 10))
            .font(.system(.body, design: .monospaced))

            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

private struct JobResultView: View {
    @ObservedObject var model: JobViewModel
    let detail: JobDetail

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            HStack {
                Image(systemName: detail.status == .succeeded ? "checkmark.circle.fill" : "xmark.circle.fill")
                    .font(.largeTitle)
                    .foregroundStyle(detail.status == .succeeded ? .green : .red)
                
                VStack(alignment: .leading) {
                    Text(detail.status == .succeeded ? "Pipeline Finished" : "Pipeline Failed")
                        .font(.title2)
                        .fontWeight(.bold)
                    Text("Job ID: \(detail.id)")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }

            if let error = detail.error {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Error Detail")
                        .font(.headline)
                    Text(error.message ?? "Unknown error")
                        .foregroundStyle(.red)
                    if let code = error.code {
                        Text("Code: \(code)")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
                .padding()
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Color.red.opacity(0.1))
                .clipShape(RoundedRectangle(cornerRadius: 8))
            }

            if let outputs = detail.outputs, !outputs.isEmpty {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Generated Artifacts")
                        .font(.headline)
                    
                    ForEach(outputs, id: \.path) { output in
                        HStack {
                            Image(systemName: icon(for: output.kind))
                            Text(output.path.split(separator: "/").last ?? "")
                            Spacer()
                            Text(output.kind)
                                .font(.caption)
                                .padding(.horizontal, 6)
                                .padding(.vertical, 2)
                                .background(Color.secondary.opacity(0.2))
                                .clipShape(Capsule())
                        }
                        .font(.system(.body, design: .monospaced))
                        .padding(8)
                        .background(Color(nsColor: .windowBackgroundColor).opacity(0.5))
                        .clipShape(RoundedRectangle(cornerRadius: 6))
                    }
                }
            }

            Spacer()

            Button("Ready for Next Job") {
                model.reset()
            }
            .frame(maxWidth: .infinity)
            .controlSize(.large)
        }
    }

    private func icon(for kind: String) -> String {
        switch kind {
        case "model": return "cube.fill"
        case "image": return "photo.fill"
        case "log": return "terminal.fill"
        default: return "doc.fill"
        }
    }
}

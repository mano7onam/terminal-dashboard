import Cocoa
import Foundation
import WebKit

/// Standalone native window with WKWebView for `python -m terminal_dashboard` (dev / no .app).
/// Usage: StandaloneWebView <url>

let args = CommandLine.arguments
guard args.count >= 2, let url = URL(string: args[1]) else {
    fputs("Usage: StandaloneWebView <url>\n", stderr)
    exit(2)
}

let app = NSApplication.shared
let delegate = StandaloneDelegate(url: url)
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()

final class StandaloneDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate {
    let startURL: URL
    var window: NSWindow!
    var webView: WKWebView!

    init(url: URL) {
        startURL = url
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        let style: NSWindow.StyleMask = [.titled, .closable, .miniaturizable, .resizable]
        window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 1180, height: 780),
            styleMask: style,
            backing: .buffered,
            defer: false
        )
        window.title = "Terminal Dashboard"
        window.minSize = NSSize(width: 720, height: 480)
        window.center()
        window.delegate = self
        window.isReleasedWhenClosed = false

        let config = WKWebViewConfiguration()
        webView = WKWebView(frame: .zero, configuration: config)
        webView.autoresizingMask = [.width, .height]
        webView.allowsBackForwardNavigationGestures = true
        window.contentView = webView
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)

        attemptLoad(triesLeft: 50)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        // Don't kill the Python server when user closes the window —
        // parent process owns the server. Just exit this helper.
        true
    }

    private func attemptLoad(triesLeft: Int) {
        let health = startURL.appendingPathComponent("api/health")
        URLSession.shared.dataTask(with: health) { [weak self] _, response, _ in
            let http = response as? HTTPURLResponse
            let ok = http != nil && (200...299).contains(http!.statusCode)
            DispatchQueue.main.async {
                guard let self = self else { return }
                if ok {
                    self.webView.load(URLRequest(url: self.startURL))
                } else if triesLeft > 0 {
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
                        self.attemptLoad(triesLeft: triesLeft - 1)
                    }
                } else {
                    self.webView.load(URLRequest(url: self.startURL))
                }
            }
        }.resume()
    }
}

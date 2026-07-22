import Cocoa
import Foundation
import WebKit

/// Menu-bar + Dock + **WKWebView app window** host for Terminal Dashboard.
/// Default UX: native window with embedded web UI (no browser tab).
/// Optional: open the same URL in a browser tab.

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular) // Dock icon stays visible
app.run()

final class AppDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate {
    private var statusItem: NSStatusItem!
    private var serverProcess: Process?
    private var port: Int = 8080
    private var windowController: DashboardWindowController?

    private var dashboardURL: URL {
        URL(string: "http://127.0.0.1:\(port)/")!
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        setupStatusItem()
        startServer()
        // Default: native WebView window (not browser)
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.6) { [weak self] in
            self?.showAppWindow()
        }
        NSApp.dockTile.badgeLabel = nil
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        // Dock click → focus / reopen app window
        showAppWindow()
        return true
    }

    func applicationWillTerminate(_ notification: Notification) {
        stopServer()
    }

    // MARK: - Menu bar

    private func setupStatusItem() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        if let button = statusItem.button {
            if let img = loadMenuBarImage() {
                button.image = img
                button.imagePosition = .imageOnly
            } else if let symbol = NSImage(
                systemSymbolName: "terminal.fill",
                accessibilityDescription: "Terminal Dashboard"
            ) {
                button.image = symbol
            } else {
                button.title = ">_"
            }
            button.toolTip = "Terminal Dashboard"
        }

        let menu = NSMenu()
        let titleItem = NSMenuItem(title: "Terminal Dashboard", action: nil, keyEquivalent: "")
        titleItem.isEnabled = false
        menu.addItem(titleItem)

        let showWin = NSMenuItem(
            title: "Show App Window",
            action: #selector(showAppWindow),
            keyEquivalent: "o"
        )
        showWin.target = self
        menu.addItem(showWin)

        menu.addItem(NSMenuItem.separator())

        let openBrowser = NSMenuItem(
            title: "Open in Browser (reuse tab)",
            action: #selector(openDashboardReuse),
            keyEquivalent: "b"
        )
        openBrowser.target = self
        menu.addItem(openBrowser)

        let openNew = NSMenuItem(
            title: "Open in Browser (new tab)",
            action: #selector(openDashboardNew),
            keyEquivalent: "n"
        )
        openNew.target = self
        menu.addItem(openNew)

        let copyItem = NSMenuItem(
            title: "Copy Dashboard URL",
            action: #selector(copyURL),
            keyEquivalent: "c"
        )
        copyItem.target = self
        menu.addItem(copyItem)

        menu.addItem(NSMenuItem.separator())

        let urlItem = NSMenuItem(title: "URL: …", action: nil, keyEquivalent: "")
        urlItem.isEnabled = false
        urlItem.tag = 100
        menu.addItem(urlItem)

        menu.addItem(NSMenuItem.separator())

        let quitItem = NSMenuItem(
            title: "Quit Terminal Dashboard",
            action: #selector(quitApp),
            keyEquivalent: "q"
        )
        quitItem.target = self
        menu.addItem(quitItem)

        statusItem.menu = menu
        updateURLMenuTitle()
    }

    private func updateURLMenuTitle() {
        if let item = statusItem.menu?.item(withTag: 100) {
            item.title = "URL: \(dashboardURL.absoluteString)"
        }
    }

    private func loadMenuBarImage() -> NSImage? {
        guard let res = Bundle.main.resourcePath else { return nil }
        let candidates = [
            res + "/MenuBarIcon.png",
            res + "/AppIcon.png",
            res + "/app/assets/AppIcon-1024.png",
        ]
        for path in candidates {
            if let img = NSImage(contentsOfFile: path) {
                let size = NSSize(width: 18, height: 18)
                let resized = NSImage(size: size)
                resized.lockFocus()
                img.draw(
                    in: NSRect(origin: .zero, size: size),
                    from: NSRect(origin: .zero, size: img.size),
                    operation: .copy,
                    fraction: 1.0
                )
                resized.unlockFocus()
                resized.isTemplate = true
                return resized
            }
        }
        return nil
    }

    // MARK: - App window (WKWebView)

    @objc func showAppWindow() {
        updateURLMenuTitle()
        if windowController == nil {
            windowController = DashboardWindowController(url: dashboardURL)
            windowController?.window?.delegate = self
        } else {
            windowController?.load(url: dashboardURL)
        }
        windowController?.showWindow(nil)
        windowController?.window?.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    func windowWillClose(_ notification: Notification) {
        // Keep app running in menu bar / Dock; window can be reopened
        // Don't nil controller if we want to reuse — actually recreate is fine
        windowController = nil
    }

    // MARK: - Server

    private func startServer() {
        port = freePort(preferred: 8080)

        guard let python = findPython() else {
            showAlert(
                title: "Python not found",
                message: "Install Xcode Command Line Tools:\n  xcode-select --install\n\nOr set TERMINAL_DASHBOARD_PYTHON."
            )
            return
        }

        guard let appDir = resourceAppDir() else {
            showAlert(title: "Missing app resources", message: "Could not find Resources/app inside the bundle.")
            return
        }

        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: python)
        // --no-open: host owns the UI (WebView); don't spawn a browser tab
        proc.arguments = ["-m", "terminal_dashboard", "--port", "\(port)", "--no-open"]
        proc.currentDirectoryURL = URL(fileURLWithPath: appDir)

        var env = ProcessInfo.processInfo.environment
        let existing = env["PYTHONPATH"] ?? ""
        env["PYTHONPATH"] = existing.isEmpty ? appDir : "\(appDir):\(existing)"
        env["TERMINAL_DASHBOARD_PORT"] = "\(port)"
        proc.environment = env

        let logPath = NSTemporaryDirectory() + "terminal-dashboard-server.log"
        FileManager.default.createFile(atPath: logPath, contents: nil)
        if let fh = FileHandle(forWritingAtPath: logPath) {
            proc.standardOutput = fh
            proc.standardError = fh
        }

        proc.terminationHandler = { [weak self] process in
            DispatchQueue.main.async {
                self?.serverProcess = nil
            }
        }

        do {
            try proc.run()
            serverProcess = proc
            updateURLMenuTitle()
        } catch {
            showAlert(title: "Failed to start server", message: error.localizedDescription)
        }
    }

    private func stopServer() {
        guard let proc = serverProcess else { return }
        if proc.isRunning {
            proc.terminate()
            DispatchQueue.global().async {
                Thread.sleep(forTimeInterval: 0.8)
                if proc.isRunning {
                    proc.interrupt()
                }
            }
        }
        serverProcess = nil
    }

    private func resourceAppDir() -> String? {
        guard let res = Bundle.main.resourcePath else { return nil }
        let app = (res as NSString).appendingPathComponent("app")
        let index = (app as NSString).appendingPathComponent("index.html")
        if FileManager.default.fileExists(atPath: index) {
            return app
        }
        return nil
    }

    private func findPython() -> String? {
        if let custom = ProcessInfo.processInfo.environment["TERMINAL_DASHBOARD_PYTHON"],
           FileManager.default.isExecutableFile(atPath: custom) {
            return custom
        }
        let candidates = [
            "/usr/bin/python3",
            "/opt/homebrew/bin/python3",
            "/usr/local/bin/python3",
        ]
        for c in candidates where FileManager.default.isExecutableFile(atPath: c) {
            return c
        }
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/usr/bin/which")
        task.arguments = ["python3"]
        let pipe = Pipe()
        task.standardOutput = pipe
        try? task.run()
        task.waitUntilExit()
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        if let s = String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines),
           !s.isEmpty, FileManager.default.isExecutableFile(atPath: s) {
            return s
        }
        return nil
    }

    private func freePort(preferred: Int) -> Int {
        func canBind(_ port: Int) -> Bool {
            let sock = socket(AF_INET, SOCK_STREAM, 0)
            guard sock >= 0 else { return false }
            defer { close(sock) }
            var yes: Int32 = 1
            setsockopt(sock, SOL_SOCKET, SO_REUSEADDR, &yes, socklen_t(MemoryLayout.size(ofValue: yes)))
            var addr = sockaddr_in()
            addr.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
            addr.sin_family = sa_family_t(AF_INET)
            addr.sin_port = UInt16(port).bigEndian
            addr.sin_addr = in_addr(s_addr: in_addr_t(0))
            let bindResult = withUnsafePointer(to: &addr) {
                $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                    Darwin.bind(sock, $0, socklen_t(MemoryLayout<sockaddr_in>.size))
                }
            }
            return bindResult == 0
        }
        if canBind(preferred) { return preferred }
        let sock = socket(AF_INET, SOCK_STREAM, 0)
        guard sock >= 0 else { return preferred }
        defer { close(sock) }
        var addr = sockaddr_in()
        addr.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
        addr.sin_family = sa_family_t(AF_INET)
        addr.sin_port = 0
        addr.sin_addr = in_addr(s_addr: in_addr_t(0))
        _ = withUnsafePointer(to: &addr) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                Darwin.bind(sock, $0, socklen_t(MemoryLayout<sockaddr_in>.size))
            }
        }
        var len = socklen_t(MemoryLayout<sockaddr_in>.size)
        _ = withUnsafeMutablePointer(to: &addr) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                getsockname(sock, $0, &len)
            }
        }
        return Int(UInt16(bigEndian: addr.sin_port))
    }

    // MARK: - Browser (optional)

    @objc private func openDashboardReuse() {
        openBrowser(mode: "reuse")
    }

    @objc private func openDashboardNew() {
        openBrowser(mode: "new")
    }

    private func openBrowser(mode: String) {
        updateURLMenuTitle()
        let api = URL(string: "http://127.0.0.1:\(port)/api/open_browser")!
        var req = URLRequest(url: api)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.timeoutInterval = 8
        let body: [String: Any] = [
            "mode": mode,
            "url": dashboardURL.absoluteString,
        ]
        req.httpBody = try? JSONSerialization.data(withJSONObject: body)

        URLSession.shared.dataTask(with: req) { [weak self] data, response, error in
            let http = response as? HTTPURLResponse
            var ok = false
            if error == nil, let http = http, (200...299).contains(http.statusCode),
               let data = data,
               let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               (json["status"] as? String) == "success" {
                ok = true
            }
            if !ok {
                DispatchQueue.main.async {
                    NSWorkspace.shared.open(self?.dashboardURL ?? api)
                }
            }
        }.resume()
    }

    @objc private func copyURL() {
        let pb = NSPasteboard.general
        pb.clearContents()
        pb.setString(dashboardURL.absoluteString, forType: .string)
    }

    @objc private func quitApp() {
        stopServer()
        NSApp.terminate(nil)
    }

    private func showAlert(title: String, message: String) {
        let alert = NSAlert()
        alert.messageText = title
        alert.informativeText = message
        alert.alertStyle = .warning
        alert.addButton(withTitle: "OK")
        alert.runModal()
    }
}

// MARK: - WKWebView window

final class DashboardWindowController: NSWindowController {
    private var webView: WKWebView!
    private var currentURL: URL

    init(url: URL) {
        currentURL = url
        let style: NSWindow.StyleMask = [.titled, .closable, .miniaturizable, .resizable]
        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 1180, height: 780),
            styleMask: style,
            backing: .buffered,
            defer: false
        )
        window.title = "Terminal Dashboard"
        window.minSize = NSSize(width: 720, height: 480)
        window.center()
        window.isReleasedWhenClosed = false
        window.titlebarAppearsTransparent = false
        window.backgroundColor = NSColor(calibratedRed: 0.06, green: 0.09, blue: 0.16, alpha: 1)

        super.init(window: window)
        setupWebView(in: window)
        load(url: url)
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    private func setupWebView(in window: NSWindow) {
        let config = WKWebViewConfiguration()
        config.preferences.setValue(true, forKey: "developerExtrasEnabled")

        webView = WKWebView(frame: window.contentView?.bounds ?? .zero, configuration: config)
        webView.autoresizingMask = [.width, .height]
        webView.allowsBackForwardNavigationGestures = true
        if #available(macOS 13.3, *) {
            webView.isInspectable = true
        }
        // Dark-ish underpage while loading
        webView.setValue(false, forKey: "drawsBackground")
        window.contentView = webView
    }

    func load(url: URL) {
        currentURL = url
        // Retry a few times until the Python server answers
        attemptLoad(url: url, triesLeft: 40)
    }

    private func attemptLoad(url: URL, triesLeft: Int) {
        let task = URLSession.shared.dataTask(with: url.appendingPathComponent("api/health")) { [weak self] _, response, _ in
            let http = response as? HTTPURLResponse
            let ok = http != nil && (200...299).contains(http!.statusCode)
            DispatchQueue.main.async {
                guard let self = self else { return }
                if ok {
                    self.webView.load(URLRequest(url: url))
                } else if triesLeft > 0 {
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.12) {
                        self.attemptLoad(url: url, triesLeft: triesLeft - 1)
                    }
                } else {
                    // Load anyway — page may still work / show connection error
                    self.webView.load(URLRequest(url: url))
                }
            }
        }
        task.resume()
    }
}

import Cocoa
import Foundation

/// Menu-bar + Dock host for Terminal Dashboard.
/// Keeps a persistent presence while the Python HTTP server runs as a child process.

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular) // Dock icon stays visible
app.run()

final class AppDelegate: NSObject, NSApplicationDelegate {
    private var statusItem: NSStatusItem!
    private var serverProcess: Process?
    private var port: Int = 8080
    private var healthTimer: Timer?

    private var dashboardURL: URL {
        URL(string: "http://127.0.0.1:\(port)/")!
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        setupStatusItem()
        startServer()
        // Open browser once after server is up — reuse existing tab if any
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.8) { [weak self] in
            self?.openDashboardReuse()
        }
        // Keep Dock tile visible / bounce once so user notices the app
        NSApp.dockTile.badgeLabel = nil
        NSApp.activate(ignoringOtherApps: false)
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        // Clicking Dock icon → reuse existing tab when possible
        openDashboardReuse()
        return true
    }

    func applicationWillTerminate(_ notification: Notification) {
        stopServer()
    }

    // MARK: - Menu bar

    private func setupStatusItem() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        if let button = statusItem.button {
            // Prefer custom icon; fallback to SF Symbol / text
            if let img = loadMenuBarImage() {
                button.image = img
                button.imagePosition = .imageOnly
            } else if let symbol = NSImage(systemSymbolName: "terminal.fill", accessibilityDescription: "Terminal Dashboard") {
                button.image = symbol
            } else {
                button.title = ">_"
            }
            button.toolTip = "Terminal Dashboard"
        }

        let menu = NSMenu()
        menu.addItem(NSMenuItem(title: "Terminal Dashboard", action: nil, keyEquivalent: ""))
        menu.items.first?.isEnabled = false

        let openReuse = NSMenuItem(
            title: "Open Dashboard (reuse tab)",
            action: #selector(openDashboardReuse),
            keyEquivalent: "o"
        )
        openReuse.target = self
        menu.addItem(openReuse)

        let openNew = NSMenuItem(
            title: "Open Dashboard in New Tab",
            action: #selector(openDashboardNew),
            keyEquivalent: "n"
        )
        openNew.target = self
        menu.addItem(openNew)

        let copyItem = NSMenuItem(title: "Copy Dashboard URL", action: #selector(copyURL), keyEquivalent: "c")
        copyItem.target = self
        menu.addItem(copyItem)

        menu.addItem(NSMenuItem.separator())

        let urlItem = NSMenuItem(title: "URL: …", action: nil, keyEquivalent: "")
        urlItem.isEnabled = false
        urlItem.tag = 100
        menu.addItem(urlItem)

        menu.addItem(NSMenuItem.separator())

        let quitItem = NSMenuItem(title: "Quit Terminal Dashboard", action: #selector(quitApp), keyEquivalent: "q")
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
        // Template 18pt icon for menu bar
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
                img.draw(in: NSRect(origin: .zero, size: size),
                         from: NSRect(origin: .zero, size: img.size),
                         operation: .copy,
                         fraction: 1.0)
                resized.unlockFocus()
                resized.isTemplate = true
                return resized
            }
        }
        return nil
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
        proc.arguments = ["-m", "terminal_dashboard", "--port", "\(port)"]
        proc.currentDirectoryURL = URL(fileURLWithPath: appDir)

        var env = ProcessInfo.processInfo.environment
        let existing = env["PYTHONPATH"] ?? ""
        env["PYTHONPATH"] = existing.isEmpty ? appDir : "\(appDir):\(existing)"
        env["TERMINAL_DASHBOARD_PORT"] = "\(port)"
        proc.environment = env

        // Log to file for debugging
        let logPath = NSTemporaryDirectory() + "terminal-dashboard-server.log"
        FileManager.default.createFile(atPath: logPath, contents: nil)
        if let fh = FileHandle(forWritingAtPath: logPath) {
            proc.standardOutput = fh
            proc.standardError = fh
        }

        proc.terminationHandler = { [weak self] process in
            DispatchQueue.main.async {
                guard let self = self else { return }
                if process.terminationStatus != 0 && process.terminationReason != .exit {
                    // unexpected crash — leave status item so user can Quit / Open
                }
                self.serverProcess = nil
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
        healthTimer?.invalidate()
        healthTimer = nil
        guard let proc = serverProcess else { return }
        if proc.isRunning {
            proc.terminate()
            // give it a moment, then force
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
        // PATH lookup
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
        // ephemeral
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

    // MARK: - Actions

    @objc private func openDashboardReuse() {
        openBrowser(mode: "reuse")
    }

    @objc private func openDashboardNew() {
        openBrowser(mode: "new")
    }

    /// mode: "reuse" finds an existing localhost:port tab; "new" always opens another tab
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
                // Fallback if API not ready yet
                DispatchQueue.main.async {
                    if mode == "new" {
                        NSWorkspace.shared.open(self?.dashboardURL ?? api)
                    } else {
                        // Still try open — may create a tab; better than nothing
                        NSWorkspace.shared.open(self?.dashboardURL ?? api)
                    }
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

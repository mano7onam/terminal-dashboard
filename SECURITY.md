# Security Policy

## Scope

Terminal Dashboard runs **locally** on your Mac. It:

- Reads process lists, TTYs, and working directories
- Runs AppleScript/JXA against terminal apps you already use
- Serves a local HTTP UI (default `localhost:8080`)

It does **not** send data to the internet.

## Recommendations

- Bind only to localhost (default behavior)
- Do not expose port 8080 to untrusted networks
- Review Automation / Accessibility grants in System Settings

## Reporting vulnerabilities

Please open a private security advisory or email the maintainer if you find a way to:

- Escape local-only intent (remote code execution via the API)
- Inject into AppleScript/JXA from untrusted session metadata
- Escalate privileges via process scanning

We will credit responsible disclosures in release notes.

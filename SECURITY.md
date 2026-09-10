# SnipGlide Python Pro — Security Architecture & Safeguards

This document describes the security model, cryptographic protection, privacy guarantees, and ReDoS isolation mechanisms implemented in SnipGlide Python Pro (Phases 1–8 Hardening).

---

## 1. AI API Key & Secret Storage

### Machine-Bound Encryption at Rest
- All AI Provider API keys (OpenAI, Gemini, OpenAI-compatible) are stored **encrypted at rest** in `settings.json`.
- Encryption uses AES-128 in CBC mode via **Fernet** with keys derived using **PBKDF2-HMAC-SHA256** (100,000 iterations) bound to the local user account and machine identity.
- Encrypted values are identified by the `enc:v1:` prefix.
- Keys are never stored in plaintext on disk, written to logs, or exposed in uncaught exception traces.

### Transparent Migration
- On startup, `load_settings()` automatically detects legacy plaintext API keys, securely encrypts them, verifies decryption integrity, and replaces the plaintext key on disk without data loss.

### Privacy & UI Masking
- The UI masks stored keys (e.g. `sk-••••••••abcd`) to prevent shoulder surfing.
- **Zero Automatic Cloud Transmission**: Clipboard history is **never** sent to any AI provider automatically.
- Any AI interaction requires explicit user initiation ("🚀 Run AI Action") and features an optional **Privacy Preview Confirmation** dialog showing the exact prompt, model, and system instructions before dispatch.

---

## 2. API Tester Secret Protection

### Credential Encryption at Rest
- Saved API requests (`saved_api_requests` SQLite table) encrypt sensitive credentials (Bearer tokens, Basic authentication passwords, custom API keys) inside `auth_data_json` before persisting to disk.
- Runtime repository calls automatically decrypt credentials only into memory for request execution.

### API History Sanitization
- Before recording executed HTTP requests in `api_history`, URLs are scrubbed of sensitive query parameters.
- Query parameters named `api_key`, `apikey`, `token`, `access_token`, `key`, `secret`, `password`, or `auth` are replaced with `[REDACTED]`.
- Sensitive authorization headers are never logged or stored in history.

---

## 3. Regex Safety & ReDoS Isolation

### Catastrophic Backtracking (ReDoS) Defense
- Python's standard `re` engine can hang indefinitely on exponential backtracking patterns such as `(a+)+$` against malicious inputs. Because standard `re` holds Python's Global Interpreter Lock (GIL) during matching, a pure in-process thread would freeze the entire application event loop.
- **Process Isolation**: SnipGlide executes regex matching and replacement within an isolated child process (`snipglide.services.regex_worker`).
- **Real Timeout Enforcement**: Execution is bounded by a strict OS-level timeout (default 2.0s). If timeout expires, the OS process is forcibly killed (`proc.kill()`), immediately freeing all CPU resources.
- **UI Non-Blocking**: The Regex Playground runs evaluations inside background `RegexMatchWorker(QThread)` with debouncing (250ms) and generation tracking to discard stale results from previous keystrokes.
- Upon timeout, a clear, non-fatal message is displayed:
  > *Regex execution timed out. Pattern may cause excessive Catastrophic Backtracking (ReDoS).*

---

## 4. Threading & Worker Lifecycle

### Cooperative Cancellation
- `QThread.terminate()` is strictly prohibited across all network, Git, and AI workers.
- All background workers implement cooperative cancellation flags (`is_cancelled` / `_is_cancelled`).
- When the user cancels an ongoing API request or AI generation:
  1. The cancellation flag is set.
  2. Result signals are disconnected to prevent race conditions.
  3. UI state is immediately restored to responsive mode.
  4. The worker safely terminates and self-destructs via `finished.connect(self.deleteLater)`.

### Non-Blocking Main UI Thread
- All external I/O and network operations are strictly prohibited during `MainWindow` initialization.
- Provider connection testing (`_test_connection`) and remote model retrieval (`_refresh_models`) run asynchronously in background threads with visual loading indicators.

---

## 5. Unicode & Arabic Safety

- `JsonTools.unescape` uses a deterministic regex parser and UTF-16 surrogate pass decoding rather than naive `unicode_escape` byte decoding.
- Full integrity is preserved for Arabic script, Persian/Urdu characters, emojis, and combined surrogate pairs.

---

## 6. Centralized Logging & Secret Redaction

- Logging is centralized via `snipglide.utils.logger.logger`.
- A dedicated `RedactingFilter` intercepts all log records and scrubs:
  - Bearer tokens (`bearer [REDACTED_TOKEN]`)
  - Basic authentication headers
  - OpenAI keys (`sk-...`)
  - Gemini keys (`AIzaSy...`)
  - PEM private keys (`-----BEGIN ... PRIVATE KEY-----`)
  - Passwords and secret assignments
- Centralized helper `redact_sensitive_text(text)` is exported for scrubbing raw strings across all modules.

---

## 7. Git & Shell Safety

- All Git operations via `GitService` use argument arrays with `shell=False`.
- On Windows, `STARTF_USESHOWWINDOW` with `SW_HIDE` is set to prevent console windows from flickering.
- Diff viewer truncates outputs beyond 2,000 lines to prevent memory exhaustion.
- Terminal Command Library is strictly a copy/reference tool with **zero automatic shell execution paths**.
- Project framework detector uses shallow inspection (root entries only) and never scans `.env` files or traverses symlink loops.

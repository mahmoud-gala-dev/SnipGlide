# SnipGlide Python Pro — Security Architecture & Safeguards

This document describes the security model, cryptographic protection, privacy guarantees, fail-closed handling, and ReDoS isolation mechanisms implemented in SnipGlide Python Pro (Release Hardening).

---

## 1. AI API Key & Secret Storage

### Fail-Closed Cryptographic Model
- `encrypt_secret(plaintext)` adheres to a strict **fail-closed** security architecture:
  - If encryption fails for any reason (cryptographic engine error, invalid key, system corruption), it **NEVER** falls back to returning the plaintext secret.
  - Instead, an explicit `ValueError` is raised, and the setting is **NOT** saved to disk.
- All AI Provider API keys (OpenAI, Gemini, Ollama, OpenAI-compatible) are stored **encrypted at rest** in `settings.json`.
- Encryption uses AES-128 in CBC mode via **Fernet** with keys derived using **PBKDF2-HMAC-SHA256** (100,000 iterations) bound to the local user account and machine identity.
- Encrypted values are identified by the `enc:v1:` versioned prefix.
- Keys are never stored in plaintext on disk, written to logs, or exposed in uncaught exception traces.

### Safe Auto-Migration
- On startup, `load_settings()` automatically detects legacy plaintext API keys (`ai_api_key`), securely encrypts them, verifies decryption integrity, and replaces the plaintext key on disk.
- The original key is never deleted or replaced until encryption is verified (`decrypt_secret(enc_key) == raw_key`).

### Privacy & UI Masking
- The UI masks stored keys (e.g. `sk-••••••••abcd`) to prevent shoulder surfing.
- **Zero Automatic Cloud Transmission**: Clipboard history is **never** sent to any AI provider automatically.
- Any AI interaction requires explicit user initiation ("🚀 Run AI Action") and features an optional **Privacy Preview Confirmation** dialog showing the exact prompt, model, and system instructions before dispatch.

---

## 2. API Tester Credential & Header Protection

### Opt-In Secure Credential Storage
- When saving API requests (`saved_api_requests` SQLite table), the user is presented with an explicit option:
  `[ ] Save credentials securely (حفظ بيانات الاعتماد والمفاتيح السرية بأمان)`
  - **Default: OFF (Unchecked)**
  - If **OFF**: authentication tokens (`token`, `password`, `value`, `secret`) and sensitive headers are stripped and not saved to disk.
  - If **ON**: credentials and sensitive headers are encrypted at rest using `encrypt_secret()`.

### Header Encryption at Rest
- Sensitive HTTP request headers (`Authorization`, `Proxy-Authorization`, `X-API-Key`, `Api-Key`, `X-Auth-Token`) are encrypted at rest inside `headers_json`.
- When requests are loaded from the repository, headers are decrypted into memory seamlessly.

### Legacy Saved Requests Backward Compatibility
- Existing saved requests created with earlier versions are detected and read seamlessly. When updated or re-saved, credentials are automatically converted to encrypted format.

### API History Sanitization
- Before recording executed HTTP requests in `api_history`, URLs are scrubbed of sensitive query parameters.
- Query parameters named `api_key`, `apikey`, `api-key`, `key`, `token`, `access_token`, `refresh_token`, `secret`, `client_secret`, `password`, `auth`, `authorization`, `bearer` have their values replaced with `[REDACTED]`.
- Preserves full URL structure including scheme, host, path, non-sensitive query parameters, and fragments.
- Sensitive authorization headers are never logged or stored in history.

---

## 3. Copy as cURL Security

- The "📋 نسخ كـ cURL" action displays a secure modal preview dialog:
  - Checkbox: `[ ] تضمين بيانات الاعتماد والمفاتيح السرية (Include credentials in cURL)`
  - **Default: OFF (Unchecked)**
  - If **OFF**: all `Authorization` values and sensitive query parameters are replaced with `[REDACTED]`.
  - If **ON**: a security warning confirmation dialog is shown before generating the raw command with sensitive credentials.

---

## 4. Regex Safety & ReDoS Isolation

### Catastrophic Backtracking (ReDoS) Defense
- Python's standard `re` engine can hang indefinitely on exponential backtracking patterns such as `(a+)+$` against malicious inputs.
- **Process Isolation**: SnipGlide executes regex matching and replacement within an isolated child process (`snipglide.services.regex_worker`).
- **Real Timeout Enforcement**: Execution is bounded by a strict OS-level timeout (default 2.0s). If timeout expires, the OS process is terminated (`proc.kill()`), immediately freeing all CPU resources.
- **Structured Non-Fatal Timeout Response**:
  > `Regex execution timed out. The pattern may cause excessive backtracking.`
- **UI Non-Blocking**: The Regex Playground runs evaluations inside background `RegexMatchWorker(QThread)` with debouncing (250ms) and generation tracking to discard stale results from previous keystrokes.

---

## 5. Threading & Worker Lifecycle

### Cooperative Cancellation
- `QThread.terminate()` is strictly prohibited across all network, Git, and AI workers.
- All background workers implement cooperative cancellation flags (`is_cancelled` / `_is_cancelled`).
- When the user cancels an ongoing API request, regex matching, or AI generation:
  1. The cancellation flag is set.
  2. Result signals are disconnected to prevent race conditions.
  3. UI state is immediately restored to responsive mode.
  4. The worker safely terminates and self-destructs via `finished.connect(self.deleteLater)`.

### Dedicated Async Workers for Provider Operations
- `AIProviderTaskWorker(QThread)` handles both `TEST_CONNECTION` and `LIST_MODELS` asynchronously without blocking the Qt UI thread.
- Action buttons are disabled with visual loading indicators (`⏳ Testing...` / `⏳`) during execution and restored on completion or cancellation.

---

## 6. Unicode, Arabic & Emoji Safety

- `JsonTools.unescape` uses a deterministic regex parser and UTF-16 surrogate pass decoding rather than naive `unicode_escape` byte decoding.
- Full integrity is preserved for Arabic script, Persian/Urdu characters, emojis, and combined surrogate pairs without text mangling.

---

## 7. Centralized Logging & Secret Redaction

- Logging is centralized via `snipglide.utils.logger.logger`.
- A dedicated `RedactingFilter` intercepts all log records and scrubs:
  - Bearer tokens (`bearer [REDACTED_TOKEN]`)
  - Basic authentication headers (`Basic [REDACTED_BASIC]`)
  - OpenAI keys (`sk-...`)
  - Gemini keys (`AIzaSy...`)
  - PEM private keys (`-----BEGIN ... PRIVATE KEY-----`)
  - Passwords and secret assignments
- Reusable helper `sanitize_log_text(text)` and `redact_sensitive_text(text)` scrub raw strings across all modules.

---

## 8. Search Resilience & Partial Fault Tolerance

- `search_repo.search_all()` queries all 10 data sources independently.
- If one source fails (e.g. transient SQLite error or missing table), the failure is logged with source name and exception type via `logger.warning`, and all remaining sources continue returning results without crashing.
- No sensitive query strings are written to logs during search exceptions.

---

## 9. Git & Shell Safety

- All Git operations via `GitService` use argument arrays with `shell=False`.
- On Windows, `STARTF_USESHOWWINDOW` with `SW_HIDE` is set to prevent console windows from flickering.
- Diff viewer truncates outputs beyond 2,000 lines to prevent memory exhaustion.
- Terminal Command Library is strictly a copy/reference tool with **zero automatic shell execution paths**.
- Project framework detector uses shallow inspection (root entries only) and never scans `.env` files or traverses symlink loops.

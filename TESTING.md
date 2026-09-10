# SnipGlide Python Pro — Testing & Quality Assurance Guide

This document details the test suites, execution procedures, test architecture, and regression verifications for SnipGlide Python Pro.

---

## 1. Overview of Test Suites

The test suite covers 163 automated test cases across 14 dedicated test modules:

| Test Module | Test Count | Description |
|---|---|---|
| `tests/test_dev_tools_service.py` | 31 | Unit tests for Developer Toolbox services (JSON beautify/minify/validate/unescape, Base64, URL encode/decode, JWT decode, UUID generation, Timestamp conversion, Hash generation, Text manipulation). |
| `tests/test_phase2_ui_integration.py` | 8 | Phase 2 Qt UI integration and tab routing. |
| `tests/test_regex_service.py` | 14 | Regex validation, flag parsing, match finding, capture groups, Unicode/Arabic/Emoji matching, zero-length matches, and ReDoS timeout enforcement. |
| `tests/test_clipboard_detector.py` | 12 | Clipboard format detector (JSON, URL, Base64, JWT, Hash, Color, Markdown, SQL, Code, Plain text). |
| `tests/test_clipboard_regression.py` | 6 | Clipboard monitor regression, duplicate detection, and memory consumption safeguards. |
| `tests/test_smart_snippets.py` | 14 | Smart Code Snippets, placeholder interpolation, dynamic dates/times, and form evaluation. |
| `tests/test_api_client.py` | 12 | API Client service URL parsing, header construction, payload serialization, and mock HTTP responses. |
| `tests/test_api_tester.py` | 14 | Standalone integration test suite with local HTTP server: GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS, auth formats, 5MB response truncation, credential encryption at rest, history query sanitization, and cURL redaction. |
| `tests/test_git_tools.py` | 6 | Git repository detection, staging status, diff viewer, recent commit history, and smart commit message heuristics. |
| `tests/test_ai_platform.py` | 7 | Multi-provider configuration validation, system prompt templates, HTTP error code mapping, and secret redaction. |
| `tests/test_projects_and_commands.py` | 4 | Developer Project auto-detection, project management, and Terminal Command Library category filtering. |
| `tests/test_unified_search.py` | 5 | Multi-source unified search, scoring heuristics, Arabic text queries, and body retrieval. |
| `tests/test_hardening_security.py` | 23 | Comprehensive security suite: fail-closed secret encryption, safe auto-migration, API credential encryption, history query redaction, ReDoS process isolation, cooperative worker cancellation, and 3-state database migration tests. |
| `tests/test_release_readiness.py` | 14 | Windows Release Candidate & Production Hardening suite: clean install, legacy DB migration, Backup v2.0 10-table coverage, VideoRecorderWorker mss thread-safety, dev tool cleanup, Windows DPAPI encryption/decryption, legacy Fernet backward compatibility, and modular package parity. |
| **TOTAL** | **163** | **100% Passed (0 Failures, 0 Errors, 0 Skipped)** |

---

## 2. How to Run the Automated Tests

### Prerequisites
Activate the project's Python virtual environment:
```powershell
.\.venv\Scripts\Activate.ps1
```

### Running the Full Regression Suite
Execute the centralized test runner:
```powershell
python run_full_tests.py
```

### Running Specific Test Modules
You can run any individual test module using standard `unittest`:
```powershell
# API Tester & Credential Security Suite
python -m unittest tests/test_api_tester.py

# Security Hardening & Fail-Closed Tests
python -m unittest tests/test_hardening_security.py

# Regex Playground & ReDoS Tests
python -m unittest tests/test_regex_service.py

# Developer Toolbox Services
python -m unittest tests/test_dev_tools_service.py
```

---

## 3. Code Compilation Verification

To verify that all Python source files and test modules compile cleanly without syntax errors:
```powershell
python -m compileall snipglide tests
```

---

## 4. Headless GUI Smoke Test

To verify that all Qt widgets, tabs, dialogs, and navigation routes instantiate without crashing:
```powershell
python smoke_test_app.py
```
This test runs in headless offscreen mode (`QT_QPA_PLATFORM=offscreen`) and verifies:
1. `MainWindowQt` initialization.
2. All 14 Developer Toolbox sub-tool tabs instantiation.
3. Command Palette routing for all developer tool actions.
4. Unified Search page execution and result rendering.

---

## 5. Security Regression Verification

The test suite explicitly enforces:
- **Fail-Closed Encryption**: Verifies that any failure in `encrypt_secret()` raises a `ValueError` and never returns plaintext fallback.
- **Zero Raw Secrets on Disk**: Verifies that `saved_api_requests` and `settings.json` persist tokens prefixed with `enc:v1:` and never in plaintext.
- **History Sanitization**: Verifies that `api_history` replaces sensitive query parameters (`token`, `api_key`, `secret`, etc.) with `[REDACTED]`.
- **ReDoS Immunity**: Verifies that catastrophic regex backtracking patterns time out within 1-2 seconds without freezing the UI.
- **Search Resilience**: Verifies that if one database table is corrupted or inaccessible, other sources continue returning results.

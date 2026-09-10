"""Benchmark script for SnipGlide Unified Search performance.
Populates an isolated SQLite database with:
- 10,000 Clipboard records
- 5,000 Snippets
- 5,000 Notes
- 1,000 Saved Regexes
- 1,000 Saved API Requests
- 500 Developer Projects
- 500 Terminal Commands

Measures real search latency across diverse query types and patterns.
"""
from __future__ import annotations

import os
import sys
import time
import tempfile
import sqlite3
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import snipglide.core.config as config
from snipglide.database.connection import initialize_database, get_connection
from snipglide.database.search_repo import search_all


def populate_benchmark_data(conn: sqlite3.Connection):
    cursor = conn.cursor()
    print("Generating synthetic dataset...")
    t0 = time.perf_counter()

    # 1. 10,000 Clipboard records
    print("  Inserting 10,000 clipboard records...")
    clipboard_data = [
        (
            f"Clipboard entry #{i}: const token_{i} = 'sample_value_{i}'; function run_{i%50}() {{ return {i}; }}",
            "text",
            f"2026-09-10 10:{i%60:02d}:00"
        )
        for i in range(10000)
    ]
    cursor.executemany(
        "INSERT INTO clipboard_history (content, content_type, copied_at) VALUES (?, ?, ?)",
        clipboard_data
    )

    # 2. 5,000 Snippets
    print("  Inserting 5,000 snippets...")
    snippet_data = [
        (
            f":snip_{i}",
            f"def helper_fn_{i}(param: str):\n    # Process data {i}\n    return param.strip()",
            f"Auto-generated helper function #{i}",
            1 if i % 20 == 0 else 0,
            "Code" if i % 2 == 0 else "Text",
            "Python" if i % 2 == 0 else "Plain Text"
        )
        for i in range(5000)
    ]
    cursor.executemany(
        """INSERT INTO snippets (shortcut, replacement, description, favorite, snippet_type, language)
           VALUES (?, ?, ?, ?, ?, ?)""",
        snippet_data
    )

    # 3. 5,000 Notes
    print("  Inserting 5,000 notes...")
    note_data = [
        (
            f"Technical Note #{i}: Architecture and Design {i}",
            f"Detailed content for note #{i}. Includes microservices, logging, caching, and database schemas {i}.",
            1 if i % 15 == 0 else 0,
            f"2026-09-10 11:{i%60:02d}:00"
        )
        for i in range(5000)
    ]
    cursor.executemany(
        "INSERT INTO notes (title, content, pinned, modified_date) VALUES (?, ?, ?, ?)",
        note_data
    )

    # 4. 1,000 Saved Regexes
    print("  Inserting 1,000 saved regexes...")
    regex_data = [
        (
            f"Regex Rule {i}",
            rf"^[a-zA-Z0-9_\.+-]+@domain_{i}\.[a-z]{{2,6}}$",
            "Email validation pattern",
            "i",
            "",
            1 if i % 10 == 0 else 0
        )
        for i in range(1000)
    ]
    cursor.executemany(
        "INSERT INTO saved_regexes (name, pattern, description, flags, replacement, favorite) VALUES (?, ?, ?, ?, ?, ?)",
        regex_data
    )

    # 5. 1,000 Saved API Requests
    print("  Inserting 1,000 saved API requests...")
    api_data = [
        (
            f"Request_{i}",
            "GET" if i % 2 == 0 else "POST",
            f"https://api.example.com/v1/resource_{i}/items?page=1",
            "[]",
            "[]",
            "none",
            "{}",
            "none",
            "",
            "Backend Collection",
            1 if i % 12 == 0 else 0
        )
        for i in range(1000)
    ]
    cursor.executemany(
        """INSERT INTO saved_api_requests
           (name, method, url, params_json, headers_json, auth_type, auth_data_json, body_type, body_content, collection_name, is_favorite)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        api_data
    )

    # 6. 500 Developer Projects
    print("  Inserting 500 developer projects...")
    proj_data = [
        (
            f"Project_{i}",
            f"D:/projects/microservice_{i}",
            "Python",
            "FastAPI",
            f"Project description #{i}",
            1 if i % 10 == 0 else 0
        )
        for i in range(500)
    ]
    cursor.executemany(
        "INSERT INTO developer_projects (name, project_path, language, framework, description, is_favorite) VALUES (?, ?, ?, ?, ?, ?)",
        proj_data
    )

    # 7. 500 Terminal Commands
    print("  Inserting 500 terminal commands...")
    cmd_data = [
        (
            f"Docker Run Container {i}",
            f"docker run -d --name service_{i} -p {8000+i}:{8000+i} myorg/image:{i}",
            f"Spin up docker container #{i}",
            "Docker",
            1 if i % 10 == 0 else 0
        )
        for i in range(500)
    ]
    cursor.executemany(
        "INSERT INTO terminal_commands (name, command, description, category, is_favorite) VALUES (?, ?, ?, ?, ?)",
        cmd_data
    )

    conn.commit()
    t_pop = time.perf_counter() - t0
    print(f"Population finished in {t_pop:.2f}s.")


def run_benchmarks():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = Path(tmpdir) / "bench_snipglide.db"
        orig_db_file = config.DB_FILE
        config.DB_FILE = test_db_path
        try:
            initialize_database()

            with get_connection() as conn:
                populate_benchmark_data(conn)

            print("\n" + "=" * 60)
            print("RUNNING UNIFIED SEARCH BENCHMARKS")
            print("Dataset Total: 23,000+ records across 7 tables")
            print("=" * 60)

            queries = [
                ("Exact shortcut", ":snip_42"),
                ("Common word in code", "helper_fn"),
                ("High-frequency text", "token_"),
                ("Technical concept", "Architecture"),
                ("HTTP API query", "resource_99"),
                ("Tool command", "docker run"),
                ("Non-existent query", "xyz_nonexistent_token_99999"),
            ]

            latencies = []

            # Warm up
            search_all("test", limit=50)

            for label, q in queries:
                times = []
                result_count = 0
                # Run each query 5 times to get min/avg
                for _ in range(5):
                    t_start = time.perf_counter()
                    results = search_all(q, limit=50)
                    dur_ms = (time.perf_counter() - t_start) * 1000.0
                    times.append(dur_ms)
                    result_count = len(results)

                avg_ms = sum(times) / len(times)
                min_ms = min(times)
                max_ms = max(times)
                latencies.extend(times)

                print(f"Query '{q}' ({label}):")
                print(f"  Results found: {result_count}")
                print(f"  Latency: avg={avg_ms:.2f}ms | min={min_ms:.2f}ms | max={max_ms:.2f}ms")

            overall_avg = sum(latencies) / len(latencies)
            overall_p95 = sorted(latencies)[int(len(latencies) * 0.95)]
            print("=" * 60)
            print(f"Overall Average Latency: {overall_avg:.2f}ms")
            print(f"P95 Latency:             {overall_p95:.2f}ms")
            print("=" * 60)

            assert overall_avg < 150.0, f"Search latency exceeded SLA! Expected < 150ms, got {overall_avg:.2f}ms"
            print("Benchmark PASSED: Unified search is well within desktop interactive latency limits (<150ms) with 23,000+ records.")
        finally:
            config.DB_FILE = orig_db_file


if __name__ == "__main__":
    run_benchmarks()

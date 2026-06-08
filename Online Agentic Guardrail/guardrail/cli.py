from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from guardrail.config import (
    DEFAULT_GUARDRAIL_MODEL,
    load_config,
    load_config_from_dict,
    GuardrailConfig,
)
from guardrail.runner import run_guardrail_check, scan_artifacts_dir
from guardrail.watcher import DEFAULT_OPENCLAW_SESSIONS_GLOB


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="guardrail",
        description="PRE_REPLY guardrail: evaluate OpenClaw trajectory safety",
    )
    subparsers = parser.add_subparsers(dest="command")

    # check subcommand
    check_parser = subparsers.add_parser(
        "check",
        help="Evaluate a single session_events.jsonl file",
    )
    check_parser.add_argument(
        "events_file",
        help="Path to session_events.jsonl",
    )
    check_parser.add_argument(
        "--config",
        default=None,
        help="Path to guardrail config JSON file",
    )
    check_parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory to write guardrail_report.json (default: next to events file)",
    )

    # scan subcommand
    scan_parser = subparsers.add_parser(
        "scan",
        help="Recursively scan a directory for session_events.jsonl files",
    )
    scan_parser.add_argument(
        "directory",
        help="Directory to scan",
    )
    scan_parser.add_argument(
        "--config",
        default=None,
        help="Path to guardrail config JSON file",
    )

    # serve subcommand
    serve_parser = subparsers.add_parser(
        "serve",
        help="Start the guardrail HTTP service",
    )
    serve_parser.add_argument(
        "--config",
        default=None,
        help="Path to guardrail config JSON file",
    )
    serve_parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Bind address (default: 0.0.0.0)",
    )
    serve_parser.add_argument(
        "--port",
        type=int,
        default=8340,
        help="Port number (default: 8340)",
    )
    serve_parser.add_argument(
        "--sessions-dir",
        default="",
        help=(
            "Session directories (single path, glob pattern with *, or comma-separated "
            f"list). Default: {DEFAULT_OPENCLAW_SESSIONS_GLOB}"
        ),
    )

    # proxy subcommand
    proxy_parser = subparsers.add_parser(
        "proxy",
        help="Run openclaw agent with PRE_REPLY guardrail interception",
    )
    proxy_parser.add_argument(
        "--message", "-m",
        required=True,
        help="Message to send to the agent",
    )
    proxy_parser.add_argument(
        "--guardrail-url",
        default="http://127.0.0.1:8340",
        help="Guardrail service URL (default: http://127.0.0.1:8340)",
    )
    proxy_parser.add_argument(
        "--agent",
        default="main",
        help="Agent name (default: main)",
    )
    proxy_parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Agent timeout in seconds (default: 120)",
    )

    # ws-proxy subcommand
    wsproxy_parser = subparsers.add_parser(
        "ws-proxy",
        help="WebSocket proxy for PRE_REPLY guardrail (use with: openclaw tui --url ws://127.0.0.1:<port>)",
    )
    wsproxy_parser.add_argument(
        "--port",
        type=int,
        default=18790,
        help="Proxy listen port (default: 18790)",
    )
    wsproxy_parser.add_argument(
        "--gateway",
        default="ws://127.0.0.1:18789",
        help="Gateway WebSocket URL (default: ws://127.0.0.1:18789)",
    )
    wsproxy_parser.add_argument(
        "--guardrail-url",
        default="http://127.0.0.1:8340",
        help="Guardrail service URL (default: http://127.0.0.1:8340)",
    )
    wsproxy_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Proxy bind address (default: 127.0.0.1)",
    )

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    config = _resolve_config(args.config if hasattr(args, "config") else None)

    if args.command == "check":
        events_path = Path(args.events_file)
        if not events_path.exists():
            print(f"Error: file not found: {events_path}", file=sys.stderr)
            return 1
        result = run_guardrail_check(events_path, config, output_dir=args.output_dir)
        _print_result(result, events_path)
        return 1 if result.prediction == 1 else 0

    if args.command == "scan":
        scan_dir = Path(args.directory)
        if not scan_dir.is_dir():
            print(f"Error: not a directory: {scan_dir}", file=sys.stderr)
            return 1
        results = scan_artifacts_dir(scan_dir, config)
        unsafe_count = sum(1 for r in results if r["prediction"] == 1)
        return 1 if unsafe_count > 0 else 0

    if args.command == "serve":
        from guardrail.server import serve
        sessions_dir = args.sessions_dir if hasattr(args, "sessions_dir") else ""
        serve(config, host=args.host, port=args.port, sessions_dir=sessions_dir)
        return 0

    if args.command == "proxy":
        from guardrail.proxy import run_proxy_cli
        return run_proxy_cli(
            message=args.message,
            guardrail_url=args.guardrail_url,
            agent=args.agent,
            timeout=args.timeout,
        )

    if args.command == "ws-proxy":
        import asyncio
        from guardrail.ws_proxy import run_proxy
        asyncio.run(run_proxy(
            listen_host=args.host,
            listen_port=args.port,
            gateway_url=args.gateway,
            guardrail_url=args.guardrail_url,
        ))
        return 0

    return 0


def _resolve_config(config_path: str | None) -> GuardrailConfig:
    """Load config from file, or from default location, or from env vars."""
    if config_path:
        return load_config(config_path)

    # Try default location next to this package
    default_path = Path(__file__).parent / "guardrail.json"
    if default_path.exists():
        return load_config(default_path)

    # Fallback: build from environment variables only
    import os
    return load_config_from_dict({
        "enabled": True,
        "api_base": os.environ.get("GUARDRAIL_API_BASE", ""),
        "model": os.environ.get("GUARDRAIL_MODEL", DEFAULT_GUARDRAIL_MODEL),
        "api_key": os.environ.get("GUARDRAIL_API_KEY", ""),
        "timeout_seconds": 60,
    })


def _print_result(result, events_path: Path) -> None:
    label = "SAFE" if result.prediction == 0 else "UNSAFE" if result.prediction == 1 else "ERROR"
    print(f"\n{'=' * 60}")
    print(f"Guardrail verdict: {label}")
    print(f"File: {events_path}")
    print(f"Model: {result.model}")
    print(f"Reason: {result.reason}")
    if result.error:
        print(f"Error: {result.error}")
    print(f"{'=' * 60}")

from __future__ import annotations

import logging
from argparse import ArgumentParser
from pathlib import Path

from agentkit.config.loader import load_full_config

from .env_check import ensure_workspace_environment
from .server import ApiServerSettings, serve


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Serve AgentKit run/verify API")
    parser.add_argument("--workspace", default=".", help="Project workspace root")
    parser.add_argument("--host", help="Bind host (defaults to runtime.yaml api_host)")
    parser.add_argument("--port", type=int, help="Bind port (defaults to runtime.yaml api_port)")
    parser.add_argument("--token", help="API token override")
    parser.add_argument("--require-token", action="store_true", help="Require API token auth")
    parser.add_argument("--log-level", help="Log level (DEBUG, INFO, WARNING, ERROR)")
    parser.add_argument("--log-file", help="Path to API log file (default from runtime.yaml api_log_file)")
    parser.add_argument("--no-log-file", action="store_true", help="Disable file logging even if runtime config enables it")
    parser.add_argument("--no-config", action="store_true", help="Do not load server defaults from configs/runtime.yaml")
    return parser


def resolve_settings(
    workspace: str,
    host: str | None = None,
    port: int | None = None,
    token: str | None = None,
    require_token: bool = False,
    no_config: bool = False,
) -> ApiServerSettings:
    workspace_path = Path(workspace).resolve()

    config_host = "127.0.0.1"
    config_port = 8787
    config_require = False
    config_token = ""
    config_log_level = "INFO"
    config_log_to_file = True
    config_log_file = ".agentkit/logs/agentkit-serve.log"

    if not no_config:
        config = load_full_config(str(workspace_path / "configs"))
        config_host = config.runtime.api_host
        config_port = config.runtime.api_port
        config_require = config.runtime.require_api_token
        config_token = config.runtime.api_token
        config_log_level = config.runtime.api_log_level
        config_log_to_file = config.runtime.api_log_to_file
        config_log_file = config.runtime.api_log_file

    settings = ApiServerSettings(
        workspace=str(workspace_path),
        host=host or config_host,
        port=port if port is not None else config_port,
        require_api_token=bool(require_token or config_require),
        api_token=token if token is not None else config_token,
        log_level=config_log_level,
        log_to_file=config_log_to_file,
        log_file=config_log_file,
    )
    if settings.require_api_token and not settings.api_token:
        raise ValueError("API token is required but missing. Set --token or configs/runtime.yaml: api_token")
    return settings


def _configure_logging(log_level: str, log_to_file: bool, log_file: str, workspace: str) -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    stream = logging.StreamHandler()
    stream.setLevel(level)
    stream.setFormatter(formatter)
    root.addHandler(stream)

    if log_to_file:
        target = Path(log_file)
        if not target.is_absolute():
            target = Path(workspace) / target
        target.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(target, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)


def run_server(
    workspace: str,
    host: str | None = None,
    port: int | None = None,
    token: str | None = None,
    require_token: bool = False,
    log_level: str | None = None,
    log_file: str | None = None,
    no_log_file: bool = False,
    no_config: bool = False,
) -> None:
    settings = resolve_settings(
        workspace=workspace,
        host=host,
        port=port,
        token=token,
        require_token=require_token,
        no_config=no_config,
    )

    ensure_workspace_environment(settings.workspace)

    effective_level = (log_level or settings.log_level or "INFO").upper()
    effective_log_file = log_file or settings.log_file
    effective_log_to_file = settings.log_to_file and (not no_log_file)

    _configure_logging(
        log_level=effective_level,
        log_to_file=effective_log_to_file,
        log_file=effective_log_file,
        workspace=settings.workspace,
    )

    settings.log_level = effective_level
    settings.log_file = effective_log_file
    settings.log_to_file = effective_log_to_file

    serve(settings)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    run_server(
        workspace=args.workspace,
        host=args.host,
        port=args.port,
        token=args.token,
        require_token=args.require_token,
        log_level=args.log_level,
        log_file=args.log_file,
        no_log_file=args.no_log_file,
        no_config=args.no_config,
    )


if __name__ == "__main__":
    main()

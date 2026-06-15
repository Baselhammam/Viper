"""
Optional FastAPI adapter launcher.

The primary way to use the capabilities layer is in-process:
    from capabilities import get_llm, get_rag

Run this script ONLY when the pipeline is in a separate process
and needs to call the backend over HTTP.

Usage:
    python run_api.py

To disable without deleting this file, set api.enabled: false in config.yaml.
"""
import sys

from app.config import cfg

if not cfg.api.enabled:
    print("API adapter is disabled (api.enabled: false in config.yaml).")
    print("Set api.enabled: true to start the HTTP server.")
    sys.exit(0)

import uvicorn

if __name__ == "__main__":
    print(f"Starting Viper API adapter on {cfg.api.host}:{cfg.api.port}")
    print("Docs: http://localhost:{}/docs".format(cfg.api.port))
    uvicorn.run(
        "api.main:app",
        host=cfg.api.host,
        port=cfg.api.port,
        reload=cfg.api.reload,
    )

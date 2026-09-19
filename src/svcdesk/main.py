# ai-generated: 100% - Claude Code (Fable 5.1) wrote this file from design/LAB1.md section 7.4; the lecturer ran it under Docker Compose
"""ASGI entry point: `uvicorn svcdesk.main:app --host 0.0.0.0 --port 8080`. Settings come from the environment."""

from .app import create_app

app = create_app()

"""
Module:      src/config.py
Description: Centralised configuration loader for the Sovereign Advisor MCP
             server. All environment variables are read here once at startup
             and exported as typed constants. Tool modules import from here
             rather than calling os.environ directly, so any rename or
             validation change only needs updating in one place.
Author:      Gayatri Anne
Created:     October 2026
"""

# ============================================================
# IMPORTS
# ============================================================
import os
import logging
from dotenv import load_dotenv

# ============================================================
# ENVIRONMENT LOADING
# ============================================================
# load_dotenv() reads the .env file in the project root and
# injects its key=value pairs into os.environ before any
# constant below is evaluated. It is a no-op if .env does not
# exist (e.g. in Azure Functions where values are injected
# by the platform at runtime) so there is no need to guard it.
# ============================================================
load_dotenv()

# ============================================================
# SERVER IDENTITY
# These values appear in the MCP tool-manifest response that
# Azure AI Foundry receives when it first connects to the
# server. Keeping them in config means they can be updated
# without touching main.py.
# ============================================================
MCP_SERVER_NAME:    str = os.getenv("MCP_SERVER_NAME",    "sovereign-advisor-mcp")
MCP_SERVER_VERSION: str = os.getenv("MCP_SERVER_VERSION", "1.0.0")

# ============================================================
# LOGGING
# ============================================================
# LOG_LEVEL is read from .env so it can be set to DEBUG
# locally without changing code. Defaults to INFO in
# production where the .env is not present.
# ============================================================
_log_level_str: str = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_LEVEL: int      = getattr(logging, _log_level_str, logging.INFO)
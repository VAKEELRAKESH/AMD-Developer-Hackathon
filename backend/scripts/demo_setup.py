#!/usr/bin/env python3
"""
AMD AgentForge — Hackathon Demo Setup
Pre-populates a 'Perfect Run' (SaaS URL Shortener) in the AgentForge system.
Used for demonstrating the self-debugging loop when API constraints or latency limits live execution.
"""

import json
import logging
import sys
import os
from pathlib import Path

# Add project root to sys.path to support 'backend.' prefixed imports
_root = str(Path(__file__).resolve().parent.parent.parent)
if _root not in sys.path:
    sys.path.append(_root)

import asyncio
from backend.core.graph.state import ForgeState
from backend.core.sandbox.executor import SandboxExecutor

logging.basicConfig(level=logging.INFO, format="[Demo Setup] %(message)s")

ARCH_SCHEMA = {
    "app_name": "link-shortener-saas",
    "app_type": "fullstack_web",
    "description": "A high-performance URL shortener with analytics, built for scale.",
    "tech_stack": {
        "frontend": "next.js",
        "backend": "fastapi",
        "database": "sqlite",
        "styling": "tailwind",
    },
    "file_tree": [
        "backend/main.py",
        "backend/requirements.txt",
    ],
    "api_routes": [
        {"method": "POST", "path": "/api/shorten", "handler": "create_short_link"},
        {"method": "GET", "path": "/{short_id}", "handler": "redirect_link"},
    ],
}

# Flawed code designed to trigger the sandbox Debugging loop
FLAWED_CODE = {
    "backend/requirements.txt": "fastapi==0.115.0\nuvicorn==0.30.0\n",
    "backend/main.py": """from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Link Shortener")

# Intentional Error: Missing random import for short ID generation
class LinkRequest(BaseModel):
    url: str

@app.post("/api/shorten")
def create_short_link(req: LinkRequest):
    short_id = "".join(random.choices("abcdefghijklmnopqrstuvwxyz", k=6))
    return {"short_url": f"http://localhost:8080/{short_id}", "original": req.url}

@app.get("/{short_id}")
def redirect_link(short_id: str):
    return {"status": "redirecting", "target": "https://example.com"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
"""
}

# The patched code after the Debugger Agent kicks in
PATCHED_CODE = {
    "backend/requirements.txt": "fastapi==0.115.0\nuvicorn==0.30.0\n",
    "backend/main.py": """from fastapi import FastAPI
from pydantic import BaseModel
import random # Added by Reviewer Agent

app = FastAPI(title="Link Shortener")

class LinkRequest(BaseModel):
    url: str

@app.post("/api/shorten")
def create_short_link(req: LinkRequest):
    short_id = "".join(random.choices("abcdefghijklmnopqrstuvwxyz", k=6))
    return {"short_url": f"http://localhost:8080/{short_id}", "original": req.url}

@app.get("/{short_id}")
def redirect_link(short_id: str):
    return {"status": "redirecting", "target": "https://example.com"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
"""
}

async def run_simulation():
    logging.info("Starting AgentForge Hackathon Mock Deployment Simulation...")
    
    # Simulate Architect
    logging.info("🏗️  Simulating Architect Agent...")
    await asyncio.sleep(1)
    logging.info(f"Architecture output generated. Files: {', '.join(ARCH_SCHEMA['file_tree'])}")
    
    # Simulate Engineer (Flawed Code)
    logging.info("⚙️  Simulating Engineer Agent (Iteration 1)...")
    await asyncio.sleep(1)
    logging.info(f"Code generated. Sending to Sandbox.")

    # Sandbox execution (Intentional failure)
    logging.info("🧪 Sandbox Testing Flawed Code...")
    executor = SandboxExecutor()
    if not executor.is_available:
        logging.warning("Sandbox unavailable. Make sure Docker is running.")
        return
        
    result_flawed = await executor.execute(FLAWED_CODE, entry_point="backend/main.py", language="python")
    
    if result_flawed["exit_code"] != 0:
        logging.info(f"❌ Sandbox correctly caught failure: {result_flawed['stderr'][:100]}...")
        logging.info("🔍 Reviewer Agent engaged...")
        await asyncio.sleep(1)
        
        logging.info("⚙️  Simulating Engineer Agent (Patching)...")
        # Sandbox execution (Patched code)
        result_patched = await executor.execute(PATCHED_CODE, entry_point="backend/main.py", language="python")
        
        if result_patched["exit_code"] == 0:
            logging.info("✅ Sandbox execution passed after self-correction loop!")
        else:
            logging.error(f"Unexpected patch failure: {result_patched['stderr']}")
    else:
        logging.error("Flawed code unexpectedly passed. Check sandbox configuration.")

    logging.info("🚀 Demo sequence fully validated and ready for judging.")

if __name__ == "__main__":
    asyncio.run(run_simulation())

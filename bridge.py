#!/usr/bin/env python3
"""
hermes-vocechat-bridge
======================
A lightweight bridge that connects VoceChat to Hermes Agent,
enabling AI-powered conversations in VoceChat with full Hermes
capabilities (memory, skills, tools).

Architecture:
    VoceChat User → Webhook → Bridge → Hermes API Server → Bridge → VoceChat Bot API

License: MIT
"""

import json
import logging
import os
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from pathlib import Path

__version__ = "1.0.0"

# ── Configuration ─────────────────────────────────────────────────────

def load_config() -> dict:
    """Load configuration from environment variables or config.yaml."""
    config = {
        "vocechat_url": os.environ.get("VOCECHAT_URL", ""),
        "vocechat_api_key": os.environ.get("VOCECHAT_API_KEY", ""),
        "hermes_url": os.environ.get("HERMES_URL", "http://localhost:8642/v1/chat/completions"),
        "hermes_key": os.environ.get("HERMES_KEY", ""),
        "listen_host": os.environ.get("LISTEN_HOST", "0.0.0.0"),
        "listen_port": int(os.environ.get("LISTEN_PORT", "8010")),
        "max_history": int(os.environ.get("MAX_HISTORY", "20")),
        "hermes_timeout": int(os.environ.get("HERMES_TIMEOUT", "120")),
        "log_level": os.environ.get("LOG_LEVEL", "INFO"),
    }

    # Try loading from config.yaml if env vars are not set
    config_path = Path(__file__).parent / "config.yaml"
    if config_path.exists() and not config["vocechat_url"]:
        try:
            import yaml  # Optional dependency
            with open(config_path) as f:
                file_config = yaml.safe_load(f)
            for key, value in file_config.items():
                if key in config and value:
                    config[key] = value
        except ImportError:
            # PyYAML not installed, try simple parsing
            with open(config_path) as f:
                for line in f:
                    line = line.strip()
                    if ":" in line and not line.startswith("#"):
                        key, _, value = line.partition(":")
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if key in config and value:
                            config[key] = value

    return config


# ── Logging ───────────────────────────────────────────────────────────

def setup_logging(level: str) -> logging.Logger:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger("bridge")


# ── Chat History Manager ──────────────────────────────────────────────

class ChatHistoryManager:
    """Thread-safe per-user chat history with bounded size."""

    def __init__(self, max_history: int = 20):
        self.max_history = max_history
        self._histories: dict[int, list] = {}
        self._lock = threading.Lock()

    def add_user_message(self, user_id: int, content: str) -> list:
        with self._lock:
            history = self._histories.setdefault(user_id, [])
            history.append({"role": "user", "content": content})
            if len(history) > self.max_history:
                history[:] = history[-self.max_history:]
            return list(history)

    def add_assistant_message(self, user_id: int, content: str):
        with self._lock:
            history = self._histories.setdefault(user_id, [])
            history.append({"role": "assistant", "content": content})
            if len(history) > self.max_history:
                history[:] = history[-self.max_history:]

    def clear(self, user_id: int):
        with self._lock:
            self._histories.pop(user_id, None)

    def clear_all(self):
        with self._lock:
            self._histories.clear()


# ── Hermes Client ─────────────────────────────────────────────────────

class HermesClient:
    """Communicates with the Hermes Agent API Server."""

    def __init__(self, url: str, key: str, timeout: int, logger: logging.Logger):
        self.url = url
        self.key = key
        self.timeout = timeout
        self.log = logger

    def chat(self, messages: list) -> str:
        payload = json.dumps({
            "model": "hermes-agent",
            "messages": messages,
        }).encode()

        req = Request(self.url, data=payload, method="POST")
        req.add_header("Authorization", f"Bearer {self.key}")
        req.add_header("Content-Type", "application/json")

        try:
            with urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read())
                return data["choices"][0]["message"]["content"]
        except HTTPError as e:
            self.log.error(f"Hermes HTTP error {e.code}: {e.reason}")
            if e.code == 429:
                return "⚠️ AI 正在忙，请稍后再试。"
            return "抱歉，AI 暂时无法回复，请稍后再试。"
        except URLError as e:
            self.log.error(f"Hermes connection error: {e.reason}")
            return "抱歉，无法连接 AI 服务，请稍后再试。"
        except Exception as e:
            self.log.error(f"Hermes unexpected error: {e}")
            return "抱歉，AI 暂时无法回复，请稍后再试。"


# ── VoceChat Client ──────────────────────────────────────────────────

class VoceChatClient:
    """Sends messages back to VoceChat via Bot API."""

    def __init__(self, url: str, api_key: str, logger: logging.Logger):
        self.url = url.rstrip("/")
        self.api_key = api_key
        self.log = logger

    def send_to_user(self, uid: int, text: str):
        self._send(f"{self.url}/api/bot/send_to_user/{uid}", text)

    def send_to_group(self, gid: int, text: str):
        self._send(f"{self.url}/api/bot/send_to_group/{gid}", text)

    def _send(self, url: str, text: str):
        req = Request(url, data=text.encode("utf-8"), method="POST")
        req.add_header("x-api-key", self.api_key)
        req.add_header("Content-Type", "text/markdown")
        try:
            with urlopen(req, timeout=30) as resp:
                self.log.debug(f"Sent message -> {resp.status}")
        except Exception as e:
            self.log.error(f"VoceChat send error: {e}")


# ── Webhook Handler ──────────────────────────────────────────────────

class WebhookHandler(BaseHTTPRequestHandler):
    """Handles VoceChat webhook events."""

    server: "BridgeServer"

    def do_GET(self):
        """Health check endpoint - VoceChat validates webhook with GET."""
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"ok")

    def do_POST(self):
        """Receive and process VoceChat webhook messages."""
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        # Respond immediately to avoid VoceChat timeout
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

        # Process message in background thread
        threading.Thread(
            target=self._process_message,
            args=(body,),
            daemon=True,
        ).start()

    def _process_message(self, body: bytes):
        bridge = self.server.bridge
        log = bridge.log

        try:
            msg = json.loads(body)
        except json.JSONDecodeError:
            log.warning("Invalid JSON received")
            return

        detail = msg.get("detail", {})
        msg_type = detail.get("type", "")
        content_type = detail.get("content_type", "")

        # Only process normal text messages
        if msg_type != "normal":
            return
        if content_type not in ("text/plain", "text/markdown"):
            return

        text = detail.get("content", "").strip()
        if not text:
            return

        from_uid = msg.get("from_uid", 0)
        target = msg.get("target", {})

        # Determine target (private chat or group)
        if "uid" in target:
            target_type = "user"
            target_id = from_uid
        elif "gid" in target:
            target_type = "group"
            target_id = target["gid"]
        else:
            return

        log.info(f"[User {from_uid}] {text[:80]}")

        # Handle special commands
        if text.strip().lower() in ("/clear", "/reset", "清除记忆"):
            bridge.history.clear(from_uid)
            reply = "✅ 对话历史已清除。"
        else:
            # Build conversation context and call Hermes
            messages = bridge.history.add_user_message(from_uid, text)
            reply = bridge.hermes.chat(messages)
            bridge.history.add_assistant_message(from_uid, reply)

        log.info(f"[Reply -> {target_type}:{target_id}] {reply[:80]}")

        # Send reply back to VoceChat
        if target_type == "user":
            bridge.vocechat.send_to_user(target_id, reply)
        else:
            bridge.vocechat.send_to_group(target_id, reply)

    def log_message(self, format, *args):
        pass  # Suppress default HTTP access logs


# ── Bridge Server ─────────────────────────────────────────────────────

class BridgeServer(HTTPServer):
    """HTTP server with bridge context attached."""

    def __init__(self, addr, handler, bridge):
        self.bridge = bridge
        super().__init__(addr, handler)


class Bridge:
    """Main bridge orchestrator."""

    def __init__(self, config: dict):
        self.config = config
        self.log = setup_logging(config["log_level"])
        self.history = ChatHistoryManager(config["max_history"])
        self.hermes = HermesClient(
            url=config["hermes_url"],
            key=config["hermes_key"],
            timeout=config["hermes_timeout"],
            logger=self.log,
        )
        self.vocechat = VoceChatClient(
            url=config["vocechat_url"],
            api_key=config["vocechat_api_key"],
            logger=self.log,
        )

    def validate_config(self) -> bool:
        errors = []
        if not self.config["vocechat_url"]:
            errors.append("VOCECHAT_URL is required")
        if not self.config["vocechat_api_key"]:
            errors.append("VOCECHAT_API_KEY is required")
        if not self.config["hermes_key"]:
            errors.append("HERMES_KEY is required")
        if errors:
            for err in errors:
                self.log.error(err)
            return False
        return True

    def run(self):
        if not self.validate_config():
            self.log.error("Configuration invalid. Exiting.")
            sys.exit(1)

        addr = (self.config["listen_host"], self.config["listen_port"])
        server = BridgeServer(addr, WebhookHandler, self)

        self.log.info(f"hermes-vocechat-bridge v{__version__}")
        self.log.info(f"Listening on {addr[0]}:{addr[1]}")
        self.log.info(f"VoceChat: {self.config['vocechat_url']}")
        self.log.info(f"Hermes:   {self.config['hermes_url']}")

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            self.log.info("Shutting down...")
            server.shutdown()


# ── Entry Point ───────────────────────────────────────────────────────

def main():
    config = load_config()
    bridge = Bridge(config)
    bridge.run()


if __name__ == "__main__":
    main()

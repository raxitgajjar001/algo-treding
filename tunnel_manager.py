import os
import subprocess
import threading
import time
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CLOUDFLARED_BIN = BASE_DIR / "cloudflared.exe"
URL_FILE = BASE_DIR / "data" / "mobile_url.txt"

class TunnelManager:
    def __init__(self, port: int = 8000):
        self.port = port
        self.process = None
        self.public_url = None
        self.is_running = False
        self._thread = None

    def start(self):
        if not CLOUDFLARED_BIN.exists():
            print(f"[Tunnel] cloudflared.exe not found at {CLOUDFLARED_BIN}")
            return None

        if self.is_running and self.public_url:
            return self.public_url

        self.is_running = True
        self._thread = threading.Thread(target=self._run_tunnel, daemon=True)
        self._thread.start()

        # Wait up to 12 seconds for the URL to be detected
        for _ in range(24):
            time.sleep(0.5)
            if self.public_url:
                break

        return self.public_url

    def _run_tunnel(self):
        cmd = [str(CLOUDFLARED_BIN), "tunnel", "--url", f"http://127.0.0.1:{self.port}"]
        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=str(BASE_DIR)
            )

            for line in iter(self.process.stdout.readline, ''):
                if not self.is_running:
                    break
                line_str = line.strip()
                if "trycloudflare.com" in line_str:
                    match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line_str)
                    if match:
                        self.public_url = match.group(0)
                        print(f"\n=======================================================")
                        print(f" [Cloudflare Tunnel] WORLDWIDE MOBILE ACCESS READY!")
                        print(f" Mobile HTTPS URL: {self.public_url}")
                        print(f"=======================================================\n")
                        try:
                            URL_FILE.parent.mkdir(parents=True, exist_ok=True)
                            URL_FILE.write_text(self.public_url, encoding="utf-8")
                        except Exception as e:
                            print(f"[Tunnel] Error saving URL: {e}")

            if self.process:
                self.process.wait()
        except Exception as e:
            print(f"[Tunnel] Exception in tunnel runner: {e}")
        finally:
            self.is_running = False

    def get_url(self) -> str:
        if self.public_url:
            return self.public_url
        if URL_FILE.exists():
            try:
                return URL_FILE.read_text(encoding="utf-8").strip()
            except Exception:
                pass
        return ""

    def stop(self):
        self.is_running = False
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=3)
            except Exception:
                self.process.kill()
            self.process = None
        self.public_url = None

tunnel_manager = TunnelManager(port=8000)

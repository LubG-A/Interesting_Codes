#!/usr/bin/env python3
import argparse
import cgi
import json
import mimetypes
import os
import secrets
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


PAGE = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>HTTP Shell</title>
  <style>
    * { box-sizing: border-box; }
    body { margin: 0; background: #111; color: #ddd; font: 15px/1.5 Consolas, Monaco, monospace; }
    main { height: 100vh; display: grid; grid-template-rows: 1fr auto auto; }
    #out { padding: 14px; overflow: auto; white-space: pre-wrap; word-break: break-word; }
    form, #tools { display: flex; gap: 8px; padding: 10px; border-top: 1px solid #333; background: #181818; }
    input { flex: 1; min-width: 0; padding: 10px; border: 1px solid #444; background: #050505; color: #eee; font: inherit; }
    button { padding: 10px 14px; border: 1px solid #555; background: #2b2b2b; color: #fff; font: inherit; cursor: pointer; }
    button.secondary { color: #ddd; background: #202020; }
    .cmd { color: #8fd; }
    .err { color: #f88; }
    .meta { color: #999; }
  </style>
</head>
<body>
<main>
  <div id="out"></div>
  <form id="form">
    <input id="cmd" autocomplete="off" autofocus placeholder="Command, e.g. pwd / whoami / ls -la">
    <button>Run</button>
  </form>
  <div id="tools">
    <input id="path" autocomplete="off" placeholder="File path for download">
    <button id="download" class="secondary" type="button">Download</button>
    <button id="upload" class="secondary" type="button">Upload</button>
    <input id="files" type="file" multiple hidden>
  </div>
</main>
<script>
const out = document.getElementById("out");
const form = document.getElementById("form");
const cmd = document.getElementById("cmd");
const pathBox = document.getElementById("path");
const uploadBtn = document.getElementById("upload");
const downloadBtn = document.getElementById("download");
const files = document.getElementById("files");
const token = new URLSearchParams(location.search).get("token") || "";
let cwd = "";

function add(text, cls = "") {
  const div = document.createElement("div");
  if (cls) div.className = cls;
  div.textContent = text;
  out.appendChild(div);
  out.scrollTop = out.scrollHeight;
}

function api(name) {
  const base = location.pathname.endsWith("/") ? location.pathname : location.pathname.replace(/[^/]*$/, "");
  return base + name;
}

async function run(command) {
  add("> " + command, "cmd");
  const res = await fetch(api("api/run"), {
    method: "POST",
    headers: {"content-type": "application/json", "x-auth-token": token},
    body: JSON.stringify({command, cwd})
  });
  const data = await res.json();
  cwd = data.cwd || cwd;
  if (data.output) add(data.output);
  if (data.error) add(data.error, "err");
  add("[exit " + data.code + "] " + cwd, "meta");
}

function currentWord() {
  const value = cmd.value;
  const pos = cmd.selectionStart;
  let start = pos;
  let end = pos;
  while (start > 0 && !/\s/.test(value[start - 1])) start--;
  while (end < value.length && !/\s/.test(value[end])) end++;
  return {value, pos, start, end, text: value.slice(start, pos)};
}

async function complete() {
  const word = currentWord();
  const res = await fetch(api("api/complete"), {
    method: "POST",
    headers: {"content-type": "application/json", "x-auth-token": token},
    body: JSON.stringify({cwd, prefix: word.text})
  });
  const data = await res.json();
  if (data.cwd) cwd = data.cwd;
  if (!data.matches || data.matches.length === 0) {
    add("[tab] no matches", "meta");
    return;
  }
  if (data.replacement && data.replacement !== word.text) {
    cmd.value = word.value.slice(0, word.start) + data.replacement + word.value.slice(word.pos);
    const caret = word.start + data.replacement.length;
    cmd.setSelectionRange(caret, caret);
  }
  if (data.matches.length > 1) add(data.matches.join("  "), "meta");
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const value = cmd.value.trim();
  if (!value) return;
  cmd.value = "";
  if (value === "clear") {
    out.textContent = "";
    return;
  }
  try {
    await run(value);
  } catch (err) {
    add(String(err), "err");
  }
});

cmd.addEventListener("keydown", async (e) => {
  if (e.key !== "Tab") return;
  e.preventDefault();
  try {
    await complete();
  } catch (err) {
    add(String(err), "err");
  }
});

uploadBtn.addEventListener("click", () => files.click());

files.addEventListener("change", async () => {
  if (!files.files.length) return;
  const formData = new FormData();
  formData.append("cwd", cwd);
  for (const file of files.files) formData.append("files", file);
  files.value = "";
  try {
    const res = await fetch(api("api/upload"), {
      method: "POST",
      headers: {"x-auth-token": token},
      body: formData
    });
    const data = await res.json();
    if (data.cwd) cwd = data.cwd;
    if (data.error) add(data.error, "err");
    if (data.saved && data.saved.length) add("[upload] " + data.saved.join(", "), "meta");
  } catch (err) {
    add(String(err), "err");
  }
});

downloadBtn.addEventListener("click", () => {
  const filePath = pathBox.value.trim() || cmd.value.trim();
  if (!filePath) return;
  const url = api("download") + "?token=" + encodeURIComponent(token)
    + "&cwd=" + encodeURIComponent(cwd)
    + "&path=" + encodeURIComponent(filePath);
  location.href = url;
});
</script>
</body>
</html>
"""


class ShellHandler(BaseHTTPRequestHandler):
    server_version = "HttpShell/1.0"

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.client_address[0], fmt % args))

    def authorized(self):
        token = getattr(self.server, "token", "")
        if not token:
            return True
        query = parse_qs(urlparse(self.path).query)
        supplied = self.headers.get("X-Auth-Token") or query.get("token", [""])[0]
        return secrets.compare_digest(supplied, token)

    def send_json(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def path_endswith(self, suffix):
        return urlparse(self.path).path.rstrip("/").endswith(suffix)

    def resolve_client_path(self, cwd, target):
        expanded = Path(os.path.expanduser(target))
        return expanded.resolve() if expanded.is_absolute() else (cwd / expanded).resolve()

    def do_GET(self):
        if not self.authorized():
            self.send_response(401)
            self.send_header("content-type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("Unauthorized. Add ?token=YOUR_TOKEN to the URL.\n".encode("utf-8"))
            return
        if self.path_endswith("/download"):
            self.handle_download()
            return
        body = PAGE.encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "text/html; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path_endswith("/api/run"):
            self.handle_run()
            return
        if self.path_endswith("/api/complete"):
            self.handle_complete()
            return
        if self.path_endswith("/api/upload"):
            self.handle_upload()
            return
        self.send_error(404)

    def handle_run(self):
        if not self.authorized():
            self.send_json(401, {"code": 401, "output": "", "error": "Unauthorized", "cwd": ""})
            return

        length = int(self.headers.get("content-length", "0"))
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            command = str(data.get("command", "")).strip()
            cwd = Path(str(data.get("cwd") or os.getcwd())).resolve()
        except Exception as exc:
            self.send_json(400, {"code": 400, "output": "", "error": str(exc), "cwd": os.getcwd()})
            return

        if not command:
            self.send_json(400, {"code": 400, "output": "", "error": "Empty command", "cwd": str(cwd)})
            return

        if command == "cd" or command.startswith("cd "):
            target = command[2:].strip().strip('"').strip("'")
            new_cwd = self.resolve_client_path(cwd, target) if target else Path.home().resolve()
            if new_cwd.is_dir():
                self.send_json(200, {"code": 0, "output": "", "error": "", "cwd": str(new_cwd)})
            else:
                self.send_json(200, {"code": 1, "output": "", "error": "Directory not found: " + str(new_cwd), "cwd": str(cwd)})
            return

        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=self.server.timeout_seconds,
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            self.send_json(200, {"code": proc.returncode, "output": output, "error": "", "cwd": str(cwd)})
        except subprocess.TimeoutExpired:
            self.send_json(200, {"code": 124, "output": "", "error": "Command timed out", "cwd": str(cwd)})
        except Exception as exc:
            self.send_json(500, {"code": 500, "output": "", "error": str(exc), "cwd": str(cwd)})

    def handle_complete(self):
        if not self.authorized():
            self.send_json(401, {"matches": [], "replacement": "", "error": "Unauthorized", "cwd": ""})
            return
        length = int(self.headers.get("content-length", "0"))
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            cwd = Path(str(data.get("cwd") or os.getcwd())).resolve()
            prefix = str(data.get("prefix") or "")
            expanded = os.path.expanduser(prefix)
            base_text, partial = os.path.split(expanded)
            base_dir = self.resolve_client_path(cwd, base_text) if base_text else cwd
            display_base = os.path.dirname(prefix)
            if display_base:
                display_base = display_base.rstrip("/\\") + os.sep
            matches = []
            for entry in sorted(base_dir.iterdir(), key=lambda p: p.name.lower()):
                if entry.name.startswith(partial):
                    suffix = os.sep if entry.is_dir() else ""
                    matches.append(display_base + entry.name + suffix)
            replacement = os.path.commonprefix(matches) if matches else prefix
            self.send_json(200, {"matches": matches[:80], "replacement": replacement, "error": "", "cwd": str(cwd)})
        except Exception as exc:
            self.send_json(200, {"matches": [], "replacement": "", "error": str(exc), "cwd": os.getcwd()})

    def handle_upload(self):
        if not self.authorized():
            self.send_json(401, {"saved": [], "error": "Unauthorized", "cwd": ""})
            return
        try:
            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={
                    "REQUEST_METHOD": "POST",
                    "CONTENT_TYPE": self.headers.get("content-type", ""),
                    "CONTENT_LENGTH": self.headers.get("content-length", "0"),
                },
            )
            cwd = Path(str(form.getfirst("cwd") or os.getcwd())).resolve()
            if not cwd.is_dir():
                self.send_json(400, {"saved": [], "error": "Directory not found: " + str(cwd), "cwd": str(cwd)})
                return
            items = form["files"] if "files" in form else []
            if not isinstance(items, list):
                items = [items]
            saved = []
            for item in items:
                if not item.filename:
                    continue
                name = os.path.basename(item.filename)
                target = cwd / name
                with target.open("wb") as fh:
                    while True:
                        chunk = item.file.read(1024 * 1024)
                        if not chunk:
                            break
                        fh.write(chunk)
                saved.append(name)
            self.send_json(200, {"saved": saved, "error": "", "cwd": str(cwd)})
        except Exception as exc:
            self.send_json(500, {"saved": [], "error": str(exc), "cwd": os.getcwd()})

    def handle_download(self):
        query = parse_qs(urlparse(self.path).query)
        cwd = Path(query.get("cwd", [os.getcwd()])[0] or os.getcwd()).resolve()
        target = query.get("path", [""])[0]
        file_path = self.resolve_client_path(cwd, target)
        if not file_path.is_file():
            self.send_response(404)
            self.send_header("content-type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(("File not found: " + str(file_path)).encode("utf-8"))
            return
        content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("content-type", content_type)
        self.send_header("content-length", str(file_path.stat().st_size))
        self.send_header("content-disposition", 'attachment; filename="%s"' % file_path.name.replace('"', ""))
        self.end_headers()
        with file_path.open("rb") as fh:
            while True:
                chunk = fh.read(1024 * 1024)
                if not chunk:
                    break
                self.wfile.write(chunk)

def main():
    parser = argparse.ArgumentParser(description="Tiny HTTP command shell")
    parser.add_argument("--host", default="127.0.0.1", help="listen host, use 0.0.0.0 for external HTTP forwarding")
    parser.add_argument("--port", type=int, default=8080, help="listen port")
    parser.add_argument("--token", default=os.environ.get("HTTP_SHELL_TOKEN", ""), help="required URL token")
    parser.add_argument("--timeout", type=int, default=60, help="command timeout seconds")
    args = parser.parse_args()

    httpd = ThreadingHTTPServer((args.host, args.port), ShellHandler)
    httpd.token = args.token
    httpd.timeout_seconds = args.timeout
    url = f"http://{args.host}:{args.port}/"
    if args.token:
        url += f"?token={args.token}"
    print("HTTP Shell listening on", url)
    print("Press Ctrl+C to stop.")
    httpd.serve_forever()


if __name__ == "__main__":
    main()

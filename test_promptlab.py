import json
import os
import re
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

passed = failed = 0


def check(name, cond):
    global passed, failed
    print(("ok   " if cond else "FAIL ") + name)
    if cond:
        passed += 1
    else:
        failed += 1


# fake openai-compatible server, echoes the system prompt back
class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        system = [m for m in body["messages"] if m["role"] == "system"][0]["content"]
        reply = "system was: " + system
        payload = {"choices": [{"message": {"role": "assistant", "content": reply}}]}
        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


server = HTTPServer(("127.0.0.1", 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
base = "http://127.0.0.1:%d/v1" % server.server_port
HERE = os.path.dirname(os.path.abspath(__file__))


def run_lab(args, stdin_data=None):
    env = dict(os.environ, OPENAI_BASE_URL=base, OPENAI_API_KEY="test")
    return subprocess.run([sys.executable, "promptlab.py"] + args,
                          capture_output=True, text=True, env=env,
                          input=stdin_data, cwd=HERE)


# text mode: labeled sections with per-reply timing
p = run_lab(["--system", "terse", "--system", "verbose", "--prompt", "hi"])
check("text mode exits 0", p.returncode == 0)
check("two labeled sections",
      "--- system 1 (gpt-4o-mini)" in p.stdout and "--- system 2 (gpt-4o-mini)" in p.stdout)
check("timing on each reply",
      len(re.findall(r"\[(\d+)ms\]", p.stdout)) == 2)
check("replies shown", "system was: terse" in p.stdout and "system was: verbose" in p.stdout)
check("prompt echoed", "prompt: hi" in p.stdout)

# multiple models multiply the runs
p = run_lab(["--system", "s", "--model", "m1", "--model", "m2", "--prompt", "hi"])
sections = re.findall(r"--- system \d+ \((\w+)\) \[\d+ms\] ---", p.stdout)
check("two models compared", sections == ["m1", "m2"])

# --json: machine-readable
p = run_lab(["--system", "terse", "--prompt", "hi", "--json"])
doc = json.loads(p.stdout)
check("json parses", isinstance(doc, dict))
check("json has prompt", doc.get("prompt") == "hi")
check("json runs shape",
      len(doc["runs"]) == 1
      and doc["runs"][0]["system"] == 1
      and doc["runs"][0]["model"] == "gpt-4o-mini"
      and isinstance(doc["runs"][0]["ms"], int)
      and doc["runs"][0]["reply"] == "system was: terse")

# --save: markdown file
out = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False)
out.close()
p = run_lab(["--system", "terse", "--system", "verbose", "--prompt", "hi", "--save", out.name])
check("save exits 0", p.returncode == 0)
md = open(out.name).read()
check("markdown header", "# promptlab comparison" in md)
check("markdown prompt", "prompt: hi" in md)
check("markdown sections",
      "## system 1 (gpt-4o-mini)" in md and "## system 2 (gpt-4o-mini)" in md)
check("markdown has timing", re.search(r"## system 1 \(gpt-4o-mini\) - \d+ms", md) is not None)
check("markdown has replies", "system was: terse" in md and "system was: verbose" in md)

# --json plus --save: stdout stays pure json, file still markdown
out2 = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False)
out2.close()
p = run_lab(["--system", "s", "--prompt", "hi", "--json", "--save", out2.name])
doc = json.loads(p.stdout)
check("json stdout pure with save", doc["prompt"] == "hi")
check("markdown still written", "# promptlab comparison" in open(out2.name).read())

# prompt from stdin
p = run_lab(["--system", "s"], stdin_data="piped question\n")
check("stdin prompt works", "prompt: piped question" in p.stdout)

# @file system prompt
sf = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False)
sf.write("from file")
sf.close()
p = run_lab(["--system", "@" + sf.name, "--prompt", "hi"])
check("@file system loads", "system was: from file" in p.stdout)

# missing system is an error
p = run_lab(["--prompt", "hi"])
check("no system rejected", p.returncode != 0)

server.shutdown()

print("\n%d passed, %d failed" % (passed, failed))
sys.exit(1 if failed else 0)

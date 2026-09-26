#!/usr/bin/env python3
"""run one prompt against several system prompts / models and compare."""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error


def complete(base_url, api_key, model, messages, timeout):
    body = {"model": model, "messages": messages}
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.load(resp)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:300]
        raise RuntimeError("api error %d: %s" % (e.code, detail))
    return payload["choices"][0]["message"].get("content") or ""


# @path loads the system prompt from a file
def load_system(arg):
    if arg.startswith("@"):
        path = arg[1:]
        try:
            with open(path) as f:
                return f.read()
        except OSError:
            sys.exit("promptlab: cant read %s" % path)
    return arg


def read_prompt(arg):
    if arg:
        return arg
    if sys.stdin.isatty():
        sys.exit("promptlab: no prompt given, use --prompt or pipe one in")
    data = sys.stdin.read().strip()
    if not data:
        sys.exit("promptlab: no prompt given, use --prompt or pipe one in")
    return data


def main(argv=None):
    p = argparse.ArgumentParser(
        description="run one prompt against several system prompts and compare")
    p.add_argument("--system", action="append", default=[],
                   help="system prompt, or @path/to/file (repeatable)")
    p.add_argument("--model", action="append", default=[],
                   help="model name (repeatable, default: gpt-4o-mini)")
    p.add_argument("--prompt", help="user prompt (or pipe it on stdin)")
    p.add_argument("--base-url",
                   default=os.environ.get("OPENAI_BASE_URL",
                                          "https://api.openai.com/v1"))
    p.add_argument("--api-key",
                   default=os.environ.get("OPENAI_API_KEY", ""))
    p.add_argument("--timeout", type=float, default=120)
    p.add_argument("--json", action="store_true",
                   help="print machine-readable json instead of labeled sections")
    p.add_argument("--save", metavar="FILE",
                   help="write the comparison to a markdown file")
    args = p.parse_args(argv)

    if not args.system:
        p.error("need at least one --system")

    systems = [load_system(s) for s in args.system]
    models = args.model or ["gpt-4o-mini"]
    prompt = read_prompt(args.prompt)

    # one run per system x model pair, timed
    runs = []
    for i, system in enumerate(systems, 1):
        for model in models:
            start = time.perf_counter()
            try:
                reply = complete(args.base_url, args.api_key, model,
                                 [{"role": "system", "content": system},
                                  {"role": "user", "content": prompt}],
                                 args.timeout)
            except (RuntimeError, urllib.error.URLError) as e:
                reply = "error: %s" % e
            ms = int((time.perf_counter() - start) * 1000)
            runs.append({"system": i, "model": model, "ms": ms, "reply": reply})

    if args.json:
        print(json.dumps({"prompt": prompt, "runs": runs}, indent=2))
    else:
        print("prompt: %s\n" % prompt)
        for run in runs:
            print("--- system %d (%s) [%dms] ---" % (run["system"], run["model"], run["ms"]))
            print(run["reply"] + "\n")

    if args.save:
        lines = ["# promptlab comparison", "", "prompt: %s" % prompt, ""]
        for run in runs:
            lines.append("## system %d (%s) - %dms" % (run["system"], run["model"], run["ms"]))
            lines.append("")
            lines.append(run["reply"])
            lines.append("")
        try:
            with open(args.save, "w") as f:
                f.write("\n".join(lines))
        except OSError as e:
            sys.exit("promptlab: cant write %s: %s" % (args.save, e))
        if not args.json:
            print("saved to %s" % args.save)


if __name__ == "__main__":
    main()

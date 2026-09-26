# promptlab

run one prompt against a few different system prompts (or models) and
compare the answers side by side. made for tuning agent system prompts:
tweak the prompt, rerun, see which version behaves better.

## usage

```
python promptlab.py \
  --system "you are terse. answer in one sentence." \
  --system @prompts/verbose.txt \
  --prompt "explain recursion"
```

prints each reply under a labeled section:

```
--- system 1 (gpt-4o-mini) ---
...

--- system 2 (gpt-4o-mini) ---
...
```

flags:

- `--system` - a system prompt string, or @path/to/file. repeat it to compare more.
- `--model` - model name, repeatable. defaults to gpt-4o-mini.
- `--prompt` - the user prompt. leave it out and pipe one on stdin instead.
- `--base-url` - api base (default: https://api.openai.com/v1, or OPENAI_BASE_URL)
- `--api-key` - defaults to OPENAI_API_KEY

works with any openai-compatible chat completions endpoint. single file,
stdlib only, no install.

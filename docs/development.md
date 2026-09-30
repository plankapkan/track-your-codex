# Development

Use Python 3.10+ from the repository root. The application and tests use only the standard library; no package installation, API keys or personal Codex logs are needed for tests or the demo. On macOS / Linux, use `python3` in the commands below.

## Tests

```sh
python -m unittest discover -s . -p "test_*.py" -v
```

Discovery includes every `test_*.py` module, including new regression tests. Fixtures use temporary directories and synthetic session records. HTTP tests use a local server with an automatically assigned port; no browser is required.

Before changing accounting algorithms, also run the focused baseline required by `AGENTS.md`:

```sh
python -m unittest -v test_monitor.py test_quota.py
```

The [CI workflow](../.github/workflows/tests.yml) runs discovery on Windows, Ubuntu and macOS with Python 3.10 and 3.14. It runs on pushes, pull requests and manual dispatch, with only `contents: read` permission. It uses the official [checkout](https://github.com/actions/checkout) and [setup-python](https://github.com/actions/setup-python) actions. A local pass does not confirm a GitHub Actions run or browser compatibility.

## Demo and interface checks

```sh
python demo.py --no-browser
```

Open <http://127.0.0.1:8767/> to inspect fictional chats, models and subagents. The demo stores its fixtures in a temporary directory and removes them on exit. Stop with Ctrl+C. Use `--port 8768` if the default port is busy, or omit `--no-browser` to open the page automatically.

After UI edits, reload the page and check both languages and themes. After Python edits, restart your demo or monitor. Keep working data in `data/` out of Git; never add private logs or credentials to test fixtures.

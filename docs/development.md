# Development

Use Python 3.10+ from the repository root. The application and tests use only the standard library; no package installation, API keys or personal Codex logs are needed for tests or the demo. On macOS / Linux, use `python3` in the commands below.

## Repository layout

```text
token_tracker/       Python package; python -m token_tracker starts the monitor
  web/               Dashboard HTML, CSS and JavaScript
tests/               Unit tests and synthetic fixtures
scripts/             Windows launchers and backend benchmark
docs/                Usage, accounting and development notes
data/                Local working database and logs (ignored by Git)
Start-monitor.cmd    Windows start shortcut
Stop-monitor.cmd     Windows stop shortcut
```

Run commands from the repository root so Python can locate the packages. Windows CMD shortcuts locate `scripts/` themselves and work from any current directory, including paths with spaces.

## Tests

```sh
python -m unittest discover -s tests -t . -p "test_*.py" -v
```

Discovery includes every `test_*.py` module, including new regression tests. Fixtures use temporary directories and synthetic session records. HTTP tests use a local server with an automatically assigned port; no browser is required.

Before changing accounting algorithms, also run the focused baseline required by `AGENTS.md`:

```sh
python -m unittest -v tests.test_monitor tests.test_quota
```

The [CI workflow](../.github/workflows/tests.yml) runs discovery on Windows, Ubuntu and macOS with Python 3.10 and 3.14. It runs on pushes, pull requests and manual dispatch, with only `contents: read` permission. It uses the official [checkout](https://github.com/actions/checkout) and [setup-python](https://github.com/actions/setup-python) actions. A local pass does not confirm a GitHub Actions run or browser compatibility.

To measure backend performance with synthetic data:

```sh
python -m scripts.benchmark_backend
```

## Demo and interface checks

```sh
python -m token_tracker.demo --no-browser
```

Open <http://127.0.0.1:8767/> to inspect fictional chats, models and subagents. The demo stores its fixtures in a temporary directory and removes them on exit. Stop with Ctrl+C. Use `--port 8768` if the default port is busy, or omit `--no-browser` to open the page automatically.

After UI edits, reload the page and check both languages and themes. After Python edits, restart your demo or monitor. Keep working data in `data/` out of Git; never add private logs or credentials to test fixtures.

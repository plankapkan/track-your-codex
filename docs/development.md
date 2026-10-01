# Development

Use Python 3.10+ from the repository root. The application and tests use only the standard library; no package installation, API keys or personal Codex logs are needed for tests or the demo. On macOS / Linux, use `python3` in the commands below.

## Repository layout

```text
token_tracker/       Python package; python -m token_tracker starts the monitor
  web/               Dashboard HTML, CSS and JavaScript
tests/               Unit tests and synthetic fixtures
scripts/             Backend benchmark
docs/                Usage, accounting and development notes
data/                Local working database and logs (ignored by Git)
start.py             Foreground launcher for all platforms; opens the browser
```

Run module commands from the repository root so Python can locate the packages. `python start.py` opens the monitor in your browser and stays in the foreground until Ctrl+C; use `--no-browser` to suppress opening. An absolute script path works from any directory without setting `PYTHONPATH`, for example `python "/path with spaces/track-your-codex/start.py"`. Working data still defaults to the repository's `data/` directory.

`python -m token_tracker` keeps the browser closed by default; `--open-browser` opts in. Both entrypoints share the same parser and support `--home`, `--data`, `--port`, `--interval`, `--once`, `--from` and `--to`. Browser opening happens after successful server startup and is skipped for help and one-shot reports. `--port 0` selects a free port; use the printed URL or `data/running.json` to find it.

## Tests

The CLI loads the last seven days on startup and extends history when a report,
export or chart requests an older boundary. A preceding week is also loaded to
preserve quota cycles and attribution blocks across the boundary. File selection
uses modification time, so a resumed old chat is included; selected journals are
parsed from the beginning to restore context and cumulative counters. Directory
enumeration still covers the archive, but unchanged old journals are not opened.
The SQLite index keeps older data; each restart bounds the in-memory quota cache
again. During a run the loaded range only expands, avoiding repeated backfills.
`index.events` counts the active accounting cache, including the boundary reserve.
Direct `Index(...)` maintenance callers retain full-history scanning unless they
pass `lazy=True`.

```sh
python -m unittest discover -s tests -t . -p "test_*.py" -v
```

Discovery includes every `test_*.py` module, including new regression tests. Fixtures use temporary directories and synthetic session records. HTTP tests use a local server with an automatically assigned port; browser calls are mocked. Launcher tests run the absolute `start.py` path from a directory with spaces without `PYTHONPATH`, exercise HTTP requests, one-shot reports and stop-marker shutdown, and verify browser policy and Ctrl+C cleanup.

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

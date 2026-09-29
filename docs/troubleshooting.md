# Troubleshooting

## Python is missing

Install Python 3.10 or newer and enable the option to add it to PATH. On Windows, the launcher first checks for Codex's bundled Python, then uses `python` from PATH. No `pip install` is needed.

If `python` opens the Microsoft Store, install Python or use the full path to an existing Python executable.

## The dashboard is empty

The monitor reads local Codex logs from `~/.codex/sessions` and `~/.codex/archived_sessions`. Use Codex on this computer, wait for the next scan, and select a period containing that activity. Cloud chats and other computers are not imported automatically.

For a different Codex directory:

```sh
python monitor.py --home /path/to/codex
```

To check the interface without your logs, run `python demo.py`.

## The page does not open

Use `http://127.0.0.1:8766/`. The server accepts connections from this computer only.

On Windows, check `data/monitor-error.log`. If the first scan takes longer than the launcher waits, leave the process running and try opening the page again. Otherwise, run `python monitor.py` in a terminal to see the error.

If another service uses port 8766, run:

```sh
python monitor.py --port 8768
```

Then open `http://127.0.0.1:8768/`.

## The allowance is missing or looks old

The monitor uses the last allowance snapshot found in the logs; it does not query your account. Check its timestamp. Missing data is not zero usage. Chat and model percentages marked ≈ are estimates and can differ from actual subscription usage.

## Report a problem

[Open an issue](https://github.com/plankapkan/track-your-codex/issues) with your OS, Python version, what you did and the error message. Remove private chat names and paths. Do not attach `auth.json`, raw session logs or your `data/` folder.

## По-русски

- Не найден Python: установите Python 3.10+ с добавлением в PATH. Windows-лаунчер также ищет встроенный Python Codex.
- Нет данных: проверьте выбранный период и наличие локальных журналов Codex. Для другого каталога используйте `--home`.
- Страница не открывается: проверьте `data/monitor-error.log` и адрес `http://127.0.0.1:8766/`. Занят порт — запустите с `--port 8768`.
- Нет лимита: в журналах может не быть свежего снимка. Монитор не запрашивает аккаунт напрямую.
- В обращении укажите систему, версию Python и текст ошибки. Уберите личные названия и пути; не прикладывайте журналы, `auth.json` и папку `data/`.

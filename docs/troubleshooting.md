# Troubleshooting

## Upgrading from v0.2.0

Stop the old monitor first and wait for it to exit. Extract v0.3.0 into a new folder, then copy the old `data/` folder into the new repository root if you want to keep your local index and settings. Launch the new folder's `Start-monitor.cmd`, or run `python -m token_tracker` from that folder.

Use a fresh folder rather than extracting over v0.2.0: obsolete root Python files, dashboard assets and PowerShell launchers must not remain alongside the new package. Keep the old folder as a backup until the new monitor works.

## Python is missing

Install Python 3.10 or newer and enable the option to add it to PATH. On Windows, the launcher first checks for Codex's bundled Python, then uses `python` from PATH. No `pip install` is needed.

If `python` opens the Microsoft Store, install Python or use the full path to an existing Python executable.

## The dashboard is empty

The monitor reads local Codex logs from `~/.codex/sessions` and `~/.codex/archived_sessions`. Use Codex on this computer, wait for the next scan, and select a period containing that activity. Cloud chats and other computers are not imported automatically.

For a different Codex directory:

```sh
python -m token_tracker --home /path/to/codex
```

To check the interface without your logs, run `python -m token_tracker.demo`.

## The page does not open

Use `http://127.0.0.1:8766/`. The server accepts connections from this computer only.

On Windows, check `data/monitor-error.log`. If the first scan takes longer than the launcher waits, leave the process running and try opening the page again. Otherwise, run `python -m token_tracker` in a terminal to see the error.

If another service uses port 8766, run:

```sh
python -m token_tracker --port 8768
```

Then open `http://127.0.0.1:8768/`.

## The allowance is missing or looks old

The monitor uses the last allowance snapshot found in the logs; it does not query your account. Check its timestamp. Missing data is not zero usage. Chat and model percentages marked ≈ are estimates and can differ from actual subscription usage.

## Report a problem

[Open an issue](https://github.com/plankapkan/track-your-codex/issues) with your OS, Python version, what you did and the error message. Remove private chat names and paths. Do not attach `auth.json`, raw session logs or your `data/` folder.

## По-русски

### Обновление с v0.2.0

Остановите старый монитор и дождитесь завершения процесса. Распакуйте v0.3.0 в новую папку. Чтобы сохранить локальный индекс и настройки, скопируйте старую `data/` в корень новой папки. Запускайте новый `Start-monitor.cmd` или выполните `python -m token_tracker` из новой папки.

Не распаковывайте поверх v0.2.0: старые Python-файлы, файлы интерфейса и PowerShell-скрипты из корня не должны оставаться рядом с новым пакетом. Сохраните старую папку как резервную копию до проверки запуска.

- Не найден Python: установите Python 3.10+ с добавлением в PATH. Windows-лаунчер также ищет встроенный Python Codex.
- Нет данных: проверьте выбранный период и наличие локальных журналов Codex. Для другого каталога используйте `--home`.
- Страница не открывается: проверьте `data/monitor-error.log` и адрес `http://127.0.0.1:8766/`. Занят порт — запустите с `--port 8768`.
- Нет лимита: в журналах может не быть свежего снимка. Монитор не запрашивает аккаунт напрямую.
- В обращении укажите систему, версию Python и текст ошибки. Уберите личные названия и пути; не прикладывайте журналы, `auth.json` и папку `data/`.

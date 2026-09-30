"""Reproducible synthetic scan timings; never accesses real Codex data."""
import argparse
import json
import statistics
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from token_tracker.indexer import Index


def measure(events=20000, files=20, repeats=3):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        home = root / 'home'
        sessions = home / 'sessions'
        sessions.mkdir(parents=True)
        first = datetime(2026, 9, 20, tzinfo=timezone.utc)
        for file_number in range(files):
            sid = f'synthetic-{file_number}'
            with (sessions / f'{sid}.jsonl').open('w', encoding='utf-8') as stream:
                rows = [dict(type='session_meta', timestamp=first.isoformat(),
                             payload=dict(id=sid, cwd=f'/demo/ai_projects/project-{file_number}', timestamp=first.isoformat())),
                        dict(type='turn_context', payload=dict(model='gpt-6.1-sol', effort='medium'))]
                for row in rows:
                    stream.write(json.dumps(row) + '\n')
                for n in range(file_number, events, files):
                    count = n // files + 1
                    last = dict(input_tokens=100, cached_input_tokens=40, output_tokens=20,
                                reasoning_output_tokens=5, total_tokens=120)
                    row = dict(type='event_msg', timestamp=(first + timedelta(seconds=n)).isoformat(),
                               payload=dict(type='token_count', info=dict(last_token_usage=last,
                                            total_token_usage={k: v * count for k, v in last.items()}),
                                            rate_limits=dict(secondary=dict(window_minutes=10080,
                                            used_percent=10 + n / max(events, 1) * 20,
                                            resets_at=int((first + timedelta(days=7)).timestamp())))))
                    stream.write(json.dumps(row) + '\n')
        index = Index(home, root / 'data')
        start = time.perf_counter()
        index.scan()
        initial = time.perf_counter() - start
        unchanged, forced = [], []
        for timings, rebuild in ((unchanged, False), (forced, True)):
            for _ in range(repeats):
                index._quota_dirty = rebuild
                start = time.perf_counter()
                index.scan()
                timings.append(time.perf_counter() - start)
        return dict(events=events, files=files, repeats=repeats,
                    initial_scan_seconds=initial,
                    unchanged_scan_median_seconds=statistics.median(unchanged),
                    forced_quota_rebuild_scan_median_seconds=statistics.median(forced),
                    unchanged_scan_seconds=unchanged, forced_quota_rebuild_scan_seconds=forced)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--events', type=int, default=20000)
    parser.add_argument('--files', type=int, default=20)
    parser.add_argument('--repeats', type=int, default=3)
    args = parser.parse_args()
    if min(args.events, args.files, args.repeats) < 1:
        parser.error('All sizes must be positive')
    print(json.dumps(measure(args.events, args.files, args.repeats), indent=2))

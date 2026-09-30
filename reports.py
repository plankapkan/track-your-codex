"""Usage reports and chart queries."""
import csv
import io
from collections import defaultdict
from datetime import datetime, timedelta
from common import MSK, RATE_DATE, RATES, blank, add, cost, synchronized
from quota import period_observation

class Reports:
    @synchronized
    def curve(self, first, final):
        """Build both chart series under one lock; socket writes happen later."""
        self.prepare_quota()
        raw = [p for p in (self.quota_cache or {}).get('curve', []) if first <= p['timestamp'] <= final]
        curve = []
        previous = None
        for point in raw:
            if previous is None or (point['used_percent'], point['reset_at']) != (previous['used_percent'], previous['reset_at']):
                if previous is not None and (not curve or curve[-1] != previous):
                    curve.append(previous)
                curve.append(point)
            previous = point
        if previous is not None and (not curve or curve[-1] != previous):
            curve.append(previous)
        return dict(curve=curve, first_time=first, final_time=final, tokens=self.token_curve(first, final))

    @synchronized
    def token_curve(self, first, final):
        """Cumulative local token totals, deduplicated before selecting the interval."""
        with self.connect() as con:
            rows = con.execute('''WITH unique_events AS (SELECT * FROM events GROUP BY event_key)
                SELECT timestamp,model,total FROM unique_events
                WHERE timestamp>=? AND timestamp<=? ORDER BY timestamp''', (first, final)).fetchall()
        if not rows:
            return dict(points=[], models=[])
        models = sorted({row['model'] for row in rows})
        totals = {model: 0 for model in models}
        points = [dict(timestamp=first, total=0, models=totals.copy())]
        # Bound the drawing size without dropping tokens or mixing model identities.
        buckets = {}
        for row in rows:
            bucket = min(399, int((row['timestamp']-first)/max(1, final-first)*400))
            entry = buckets.setdefault(bucket, dict(timestamp=row['timestamp'], models=defaultdict(int)))
            entry['timestamp'] = max(entry['timestamp'], row['timestamp'])
            entry['models'][row['model']] += row['total']
        for entry in buckets.values():
            for model, value in entry['models'].items():
                totals[model] += value
            points.append(dict(timestamp=entry['timestamp'], total=sum(totals.values()), models=totals.copy()))
        if points[-1]['timestamp'] < final:
            points.append(dict(timestamp=final, total=sum(totals.values()), models=totals.copy()))
        return dict(points=points, models=sorted(models, key=lambda model: (-totals[model], model)))

    @synchronized
    def report(self, start, end, selected_project='', model='', grouped=True, cycle=False, hours=None, start_time=None, end_time=None):
        self.prepare_quota()
        first = datetime.strptime(start, '%Y-%m-%d').replace(tzinfo=MSK)
        final = datetime.strptime(end, '%Y-%m-%d').replace(tzinfo=MSK) + timedelta(days=1)
        if final <= first:
            raise ValueError('Начало периода должно быть не позже конца')
        if hours is not None:
            hours = int(hours)
            if not 1 <= hours <= 365 * 24:
                raise ValueError('Период должен быть от 1 часа до 365 дней')
            cycle = False
            final = datetime.now(MSK)
            first = final - timedelta(hours=hours)
            start, end = first.date().isoformat(), final.date().isoformat()
        if start_time is not None or end_time is not None:
            if not start_time or not end_time:
                raise ValueError('Укажите начало и конец периода')
            first = datetime.fromisoformat(start_time)
            final = datetime.fromisoformat(end_time)
            first = first.replace(tzinfo=MSK) if first.tzinfo is None else first.astimezone(MSK)
            final = final.replace(tzinfo=MSK) if final.tzinfo is None else final.astimezone(MSK)
            if final <= first:
                raise ValueError('Конец периода должен быть позже начала')
            cycle = False
            start, end = first.date().isoformat(), final.date().isoformat()
        con = self.connect()
        try:
            cache=self.quota_cache
            if cycle and cache and cache['latest']:
                first=datetime.fromtimestamp(cache['latest']['reset_at']-10080*60,MSK)
                final=datetime.now(MSK)
                start,end=first.date().isoformat(),final.date().isoformat()
            meta = {r['id']: dict(r) for r in con.execute('SELECT * FROM threads')}
            where, params = 'timestamp>=? AND timestamp<?', [first.timestamp(), final.timestamp()]
            if model:
                where += ' AND model=?'
                params.append(model)
            rows = con.execute(f'''WITH unique_events AS (SELECT * FROM events GROUP BY event_key)
                SELECT thread,model,effort,SUM(calls) AS calls,
                SUM(input) AS input,SUM(cached) AS cached,SUM(fresh) AS fresh,
                SUM(output) AS output,SUM(reasoning) AS reasoning,SUM(total) AS total
                FROM unique_events WHERE {where} GROUP BY thread,model,effort''', params).fetchall()
            summary, models, chats, projects = blank(), {}, {}, {}
            quota=self.quota_cache or dict(allocations={},windows=[],blocks=[],latest=None,curve=[],notes=[],covered=set(),events=[])
            pp_by_group=defaultdict(float)
            covered_by_group=defaultdict(int)
            for event in quota['events']:
                if not first.timestamp() <= event['timestamp'] < final.timestamp():
                    continue
                key=(event['thread'],event['model'],event['effort'])
                pp_by_group[key]+=quota['allocations'].get(event['event_key'],0.)
                if event['event_key'] in quota['covered']:
                    covered_by_group[key]+=event['total']
            summary.update(quota_pp=0.,quota_covered_tokens=0)
            estimated, priced_tokens = 0., 0
            for raw in rows:
                row = dict(raw)
                sid = row['thread']
                own = meta.get(sid, dict(id=sid, title=sid, project='Без проекта', parent=None, source='unknown'))
                root = sid
                seen = set()
                while grouped and root in meta and meta[root]['parent'] and root not in seen:
                    seen.add(root)
                    root = meta[root]['parent']
                owner = meta.get(root, own)
                proj = owner['project'] if grouped else own['project']
                if selected_project and proj != selected_project:
                    continue
                quota_key=(sid,row['model'],row['effort'])
                pp=pp_by_group[quota_key]
                covered_tokens=covered_by_group[quota_key]
                summary['quota_pp']+=pp
                summary['quota_covered_tokens']+=covered_tokens
                add(summary, row)
                mk = (row['model'], row['effort'])
                if mk not in models:
                    models[mk] = dict(model=mk[0], effort=mk[1], **blank(),quota_pp=0.,quota_covered_tokens=0, estimated_credits=0 if mk[0] in RATES else None)
                add(models[mk], row)
                models[mk]['quota_pp']+=pp
                models[mk]['quota_covered_tokens']+=covered_tokens
                if row['model'] in RATES:
                    value = cost(row, RATES[row['model']])
                    estimated += value
                    priced_tokens += row['total']
                    models[mk]['estimated_credits'] += value
                if proj not in projects:
                    projects[proj] = dict(project=proj, **blank(),quota_pp=0.,quota_covered_tokens=0)
                add(projects[proj], row)
                projects[proj]['quota_pp']+=pp
                projects[proj]['quota_covered_tokens']+=covered_tokens
                ck = (root if grouped else sid, row['model'], row['effort'])
                if ck not in chats:
                    chats[ck] = dict(thread=ck[0], title=owner['title'], project=proj,
                        model=row['model'], effort=row['effort'], **blank(),
                        main_calls=0, subagent_calls=0,quota_pp=0.,quota_covered_tokens=0, estimated_credits=0 if row['model'] in RATES else None)
                add(chats[ck], row)
                chats[ck]['quota_pp']+=pp
                chats[ck]['quota_covered_tokens']+=covered_tokens
                chats[ck]['subagent_calls' if own.get('parent') else 'main_calls'] += row['calls']
                if row['model'] in RATES:
                    chats[ck]['estimated_credits'] += cost(row, RATES[row['model']])
            diagnostics = [dict(r) for r in con.execute('SELECT message,COUNT(*) AS count FROM diagnostics GROUP BY message')]
            last = con.execute("SELECT value FROM settings WHERE key='last_scan'").fetchone()
            observation=period_observation(quota,first.timestamp(),final.timestamp())
            blocks=[b for b in quota['blocks'] if b['end']>=first.timestamp() and b['start']<final.timestamp()]
            quota_view=dict(latest=quota['latest'],period=observation,
                account_scope='all_local_account_observations',estimated_selected_pp=summary['quota_pp'],
                unassigned_block_pp=sum(b['unassigned_pp'] for b in blocks),
                curve=[p for p in quota['curve'] if first.timestamp()<=p['timestamp']<final.timestamp()],
                preliminary=any(b['preliminary'] and b['assigned_pp'] for b in blocks),
                notes=quota['notes'],windows=quota['windows'],
                assumptions=['credit_weights_standard','concurrent_chats','rounded_shared_account_counter','local_logs_only'])
            # Compress flat portions for the graph only; full samples remain in the database.
            raw_curve=quota_view['curve']
            short=[]
            previous=None
            for point in raw_curve:
                if previous is None or (point['used_percent'],point['reset_at'])!=(previous['used_percent'],previous['reset_at']):
                    if previous is not None and (not short or short[-1]!=previous):short.append(previous)
                    short.append(point)
                previous=point
            if previous is not None and (not short or short[-1]!=previous):short.append(previous)
            quota_view['curve']=short
            return dict(range=dict(start=start, end=end,cycle=cycle,first_time=first.timestamp(),final_time=final.timestamp()), summary=summary,quota=quota_view,
                models=sorted(models.values(), key=lambda r: -r['total']),
                chats=sorted(chats.values(), key=lambda r: -r['total']),
                projects=sorted(projects.values(), key=lambda r: -r['total']),
                options=dict(projects=sorted({r['project'] for r in meta.values()}),
                             models=[r[0] for r in con.execute('SELECT DISTINCT model FROM events ORDER BY model')]),
                index=dict(**self.status, indexed_files=con.execute('SELECT COUNT(*) FROM files').fetchone()[0],
                           events=con.execute('SELECT COUNT(DISTINCT event_key) FROM events').fetchone()[0]),
                snapshot=self.status['last_scan'] or (last['value'] if last else None),
                diagnostics=diagnostics,
                pricing=dict(date=RATE_DATE, source='https://learn.chatgpt.com/docs/pricing#token-rates',
                    estimated_credits=estimated, priced_tokens=priced_tokens,
                    astra_same_tokens=cost(summary, RATES['gpt-6-astra']),
                    sol61_same_tokens=cost(summary, RATES['gpt-6.1-sol']),
                    comparison=[dict(model=name,credits=cost(summary,RATES[name])) for name in
                        sorted({'gpt-6-astra','gpt-6.1-sol',*[r['model'] for r in models.values()]}) if name in RATES]))
        finally:
            con.close()

def csv_text(rows):
    if not rows:
        return '\ufeff'
    stream = io.StringIO(newline='')
    keys = list(rows[0])
    writer = csv.DictWriter(stream, fieldnames=keys)
    writer.writeheader()
    for row in rows:
        safe = {k: ("'" + v if isinstance(v, str) and v.lstrip().startswith(('=', '+', '-', '@')) else v)
                for k, v in row.items()}
        writer.writerow(safe)
    return '\ufeff' + stream.getvalue()

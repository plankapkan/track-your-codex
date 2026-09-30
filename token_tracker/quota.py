"""Conditional attribution of observed account quota changes, never per-request billing."""
from collections import defaultdict

WEEK = 10080 * 60
RESET_TOLERANCE = 60  # The service can return reset timestamps differing by a few seconds.
BLOCK_PP = 5

def build_quota(samples, events, rates):
    """Use global, unfiltered history. Filtering must happen after attribution.

    events have timestamp/thread/model/effort and fresh/cached/output/event_key.
    Return allocation by event_key and account observations / conditional blocks.
    """
    allocation = defaultdict(float)
    if not samples:
        return dict(allocations=allocation, windows=[], blocks=[], latest=None, curve=[], notes=[], covered=set())
    # Prefer the account's Codex limit, and keep other advertised limits separate.
    limit = 'codex' if any(r['limit_id'] == 'codex' for r in samples) else max(samples, key=lambda r:r['timestamp'])['limit_id']
    samples = [s for s in samples if s['limit_id'] == limit]
    clusters = []
    for sample in sorted(samples, key=lambda s:(s['reset_at'],s['timestamp'])):
        if not clusters or sample['reset_at'] - clusters[-1]['reset_at'] > RESET_TOLERANCE:
            clusters.append(dict(reset_at=sample['reset_at'], samples=[]))
        clusters[-1]['samples'].append(sample)
    windows, blocks, notes, curve = [], [], [], []
    covered = set()
    ordered_events = sorted(events, key=lambda e:e['timestamp'])
    import bisect
    times = [e['timestamp'] for e in ordered_events]
    for cluster_index,cluster in enumerate(clusters):
        # Same provider snapshot may be copied to an archive or occur in several logs.
        unique = {(s['timestamp'],s['used_percent']):s for s in cluster['samples']}
        rows = sorted(unique.values(), key=lambda s:s['timestamp'])
        if cluster_index+1 < len(clusters):
            next_start=clusters[cluster_index+1]['reset_at']-WEEK
            rows=[s for s in rows if s['timestamp']<next_start]
        if not rows:
            continue
        first, last = rows[0], rows[-1]
        start_time, base, high = first['timestamp'], first['used_percent'], first['used_percent']
        base_initial = base
        suspect, drops, stale = False, 0, 0
        window_blocks = []
        def close(end_time, end_used, preliminary):
            nonlocal start_time, base, suspect
            delta = end_used - base
            lo, hi = bisect.bisect_right(times,start_time), bisect.bisect_right(times,end_time)
            local = ordered_events[lo:hi]
            weights = []
            unknown = False
            for event in local:
                rate = rates.get(event['model'])
                if rate is None:
                    unknown = True
                    continue
                weight = (event['fresh']*rate[0]+event['cached']*rate[1]+event['output']*rate[2])/1_000_000
                weights.append((event,weight))
            weight_total = sum(w for _,w in weights)
            good = delta > 0 and not suspect and not unknown and weight_total > 0
            reason = ('decreasing_snapshots' if suspect else 'unknown_model' if unknown else
                      'no_local_tokens' if not weight_total else 'below_resolution' if not delta else None)
            if good:
                for event,weight in weights:
                    allocation[event['event_key']] += delta*weight/weight_total
                    covered.add(event['event_key'])
            block = dict(start=start_time, end=end_time, delta_pp=delta,
                assigned_pp=delta if good else 0., unassigned_pp=0. if good else delta,
                preliminary=preliminary, reason=reason, weight=weight_total,
                quota_per_credit=delta/weight_total if good else None,
                reset_at=cluster['reset_at'], limit_id=limit)
            blocks.append(block)
            window_blocks.append(block)
            start_time, base, suspect = end_time, end_used, False
        for index,row in enumerate(rows):
            curve.append(dict(timestamp=row['timestamp'], used_percent=row['used_percent'],reset_at=cluster['reset_at']))
            if row['used_percent'] < high:
                # Small dips recovering promptly are conditionally treated as lag,
                # based on inspected concurrent logs; this is an explicit heuristic.
                recovered=False
                if high-row['used_percent']<=1:
                    for future in rows[index+1:]:
                        if future['timestamp']-row['timestamp']>120:break
                        if future['used_percent']>=high:
                            recovered=True
                            break
                if recovered:
                    stale+=1
                else:
                    suspect = True
                    drops += 1
            high = max(high,row['used_percent'])
            if high-base >= BLOCK_PP:
                close(row['timestamp'], high, False)
        if last['timestamp'] > start_time:
            close(last['timestamp'], high, True)
        windows.append(dict(reset_at=cluster['reset_at'], first_time=first['timestamp'],
            last_time=last['timestamp'], baseline_pp=base_initial, latest_used_percent=last['used_percent'],
            observed_growth_pp=high-base_initial,
            assigned_pp=sum(b['assigned_pp'] for b in window_blocks),
            unassigned_pp=sum(b['unassigned_pp'] for b in window_blocks), decreases=drops,assumed_stale=stale))
        if drops:
            notes.append(dict(reset_at=cluster['reset_at'],type='decreasing_snapshots',count=drops))
        if stale:
            notes.append(dict(reset_at=cluster['reset_at'],type='assumed_stale',count=stale))
    latest = max(samples,key=lambda s:s['timestamp'])
    return dict(allocations=allocation,windows=windows,blocks=blocks,latest=latest,
                curve=sorted(curve,key=lambda p:p['timestamp']),notes=notes,covered=covered)

def period_observation(quota, first, final):
    """Measured positive net increases with boundary snapshots; resets never subtract spending."""
    growth, initial, unassigned = 0., 0., 0.
    windows = []
    for window in quota['windows']:
        points = [p for p in quota['curve'] if p['reset_at']==window['reset_at']]
        before = [p for p in points if p['timestamp'] < first]
        inside = [p for p in points if first <= p['timestamp'] < final]
        if not inside:
            continue
        # A lagging snapshot at the date boundary must not count its recovery again.
        base = max(p['used_percent'] for p in before) if before else inside[0]['used_percent']
        # Within suspect windows, the high-water change is explicitly diagnostic.
        delta = max(0.,max(p['used_percent'] for p in inside)-base)
        growth += delta
        if not before:
            initial += base
        windows.append(dict(reset_at=window['reset_at'],growth_pp=delta,baseline_pp=base,
                            decreases=window['decreases']))
    return dict(observed_growth_pp=growth,baseline_not_attributed_pp=initial,windows=windows)

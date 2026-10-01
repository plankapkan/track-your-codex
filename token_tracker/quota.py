"""Conditional attribution of observed account quota changes, never per-request billing."""
from collections import defaultdict

WEEK = 10080 * 60
RESET_TOLERANCE = 60  # The service can return reset timestamps differing by a few seconds.
BLOCK_PP = 5

def consumption_pace(quota, now, first=None, final=None):
    """Time-average observed account growth within the selected range.

    Clip valid intervals to range boundaries. Pauses contribute time; missing
    history, resets and decreases do not. Do not trim real bursts: averaging
    their growth over observed time smooths peaks without losing consumption.
    """
    final = min(now, now if final is None else final)
    first = final-10800 if first is None else first
    result = dict(status='insufficient', pp_per_hour=None, eta_seconds=None,
                  reset_before_exhaustion=None, span_seconds=0, growth_pp=0,
                  sample_age_seconds=None, range_seconds=max(0, final-first),
                  coverage_percent=0, forecast_status='insufficient')
    latest = quota.get('latest')
    if latest is None:
        return result
    age = max(0, now-latest['timestamp'])
    result['sample_age_seconds'] = age
    if final <= first:
        return result
    # build_quota already canonicalizes reset timestamp jitter and limit IDs.
    points = [p for p in quota['curve']
              if first-1800 <= p['timestamp'] <= min(now, final+1800)]
    rows = []
    for index, point in enumerate(points):
        if rows and rows[-1] is not None and 0 < rows[-1]['used_percent']-point['used_percent'] <= 1:
            if point['reset_at'] == rows[-1]['reset_at'] and any(
                   future['reset_at'] == point['reset_at']
                   and future['used_percent'] >= rows[-1]['used_percent']
                   for future in points[index+1:]
                   if future['timestamp']-point['timestamp'] <= 120):
                continue  # Same short recovered lag heuristic as attribution.
        if rows and rows[-1] is not None and point['timestamp'] == rows[-1]['timestamp']:
            if point['used_percent'] != rows[-1]['used_percent']:
                rows[-1] = None  # Exclude both intervals at conflicting readings.
            continue
        rows.append(point)
    growth = span = 0.
    high = None
    reset_at = None
    for left, right in zip(rows, rows[1:]):
        if left is None or right is None:
            continue
        duration = right['timestamp']-left['timestamp']
        delta = right['used_percent']-left['used_percent']
        if reset_at != left['reset_at']:
            high = left['used_percent']
            reset_at = left['reset_at']
        high = max(high, left['used_percent'])
        # Recovery from a persistent dip is not new spending. Use only growth
        # above the cycle's previously observed high-water mark.
        delta = min(delta, max(0, right['used_percent']-high))
        if right['reset_at'] == reset_at:
            high = max(high, right['used_percent'])
        if (not 0 < duration <= 1800 or delta < 0
                or left['reset_at'] != right['reset_at']):
            continue
        start = max(first, left['timestamp'])
        stop = min(final, right['timestamp'])
        if stop <= start:
            continue
        growth += delta*(stop-start)/duration
        span += stop-start
    result.update(span_seconds=span, growth_pp=growth,
                  coverage_percent=span/(final-first)*100)
    if span < 900:
        return result
    if growth < 2:
        result['status'] = 'below_resolution'
        return result
    speed = growth/span*3600
    result.update(status='ok', pp_per_hour=speed)
    # Historical averages remain useful when the latest account reading is
    # stale. Only a forecast needs a fresh balance in the current cycle.
    if now >= latest['reset_at']:
        result['forecast_status'] = 'reset_due'
        return result
    if age > 900:
        result['forecast_status'] = 'stale'
        return result
    if latest['used_percent'] >= 100:
        result.update(forecast_status='exhausted', eta_seconds=0)
        return result
    eta = (100-latest['used_percent'])/speed*3600
    result.update(forecast_status='ok', eta_seconds=eta,
                  reset_before_exhaustion=now+eta >= latest['reset_at'])
    return result

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

import json
import tempfile
import unittest
import threading
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from token_tracker.indexer import Index
from token_tracker.reports import csv_text
from token_tracker.server import Handler, LocalHTTPServer

def meta(sid, created='2026-09-29T10:00:00Z', parent=None):
    payload = dict(id=sid, timestamp=created, cwd='C:\\Users\\Example\\Documents\\ai_projects\\sample-project')
    if parent:
        payload['parent_thread_id'] = parent
        payload['source'] = {'subagent': {'thread_spawn': {'parent_thread_id': parent}}}
    return dict(type='session_meta', timestamp=created, payload=payload)

def context(model='gpt-6.1-sol', turn='turn1'):
    return dict(type='turn_context', payload=dict(model=model, effort='medium', turn_id=turn))

def usage(timestamp, fresh, cached, output, total=None, reasoning=0):
    last = dict(input_tokens=fresh+cached, cached_input_tokens=cached,
        output_tokens=output, reasoning_output_tokens=reasoning, total_tokens=fresh+cached+output)
    return dict(type='event_msg', timestamp=timestamp, payload=dict(type='token_count',
        info=dict(total_token_usage=total or last, last_token_usage=last)))

def plus(a, b):
    return {k: a.get(k,0)+b.get(k,0) for k in a}

class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.home = self.root/'home'
        (self.home/'sessions').mkdir(parents=True)
        self.index = Index(self.home, self.root/'data')

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, events, append=False):
        path = self.home/'sessions'/name
        with path.open('a' if append else 'w', encoding='utf-8') as stream:
            for event in events:
                stream.write(json.dumps(event, ensure_ascii=False)+'\n')
        return path

    def report(self, grouped=True, start='2026-09-29', end='2026-09-29', **kwargs):
        return self.index.report(start, end, grouped=grouped, **kwargs)

    def test_rolling_hour_periods(self):
        now = datetime.now(timezone.utc)
        events = [meta('hours', created=(now-timedelta(days=2)).isoformat()), context()]
        total = None
        for age in (25, 6, 1):
            event = usage((now-timedelta(hours=age)).isoformat(), 10, 0, 5)
            last = event['payload']['info']['last_token_usage']
            total = plus(total, last) if total else last.copy()
            event['payload']['info']['total_token_usage'] = total.copy()
            events.append(event)
        self.write('hours.jsonl', events)
        self.index.scan()
        for hours, expected in ((1, 0), (5, 15), (12, 30), (24, 30), (48, 45), (720, 45)):
            data = self.report(hours=hours, cycle=True)
            self.assertEqual(data['summary']['total'], expected)
            self.assertFalse(data['range']['cycle'])
            self.assertAlmostEqual(data['range']['final_time']-data['range']['first_time'], hours*3600)
        with self.assertRaises(ValueError):
            self.report(hours=0)
        with self.assertRaises(ValueError):
            self.report(hours=8761)

    def test_custom_datetime_period(self):
        a = usage('2026-09-29T10:01:00Z', 10, 0, 5)
        b = usage('2026-09-29T10:02:00Z', 10, 0, 5)
        b['payload']['info']['total_token_usage'] = plus(a['payload']['info']['last_token_usage'], b['payload']['info']['last_token_usage'])
        self.write('custom.jsonl', [meta('custom'), context(), a, b])
        self.index.scan()
        for offset in ('', '+03:00'):
            data = self.report(start_time='2026-09-29T13:01'+offset, end_time='2026-09-29T13:02'+offset, cycle=True)
            self.assertEqual(data['summary']['total'], 15)
            self.assertEqual(data['range']['final_time']-data['range']['first_time'], 60)
            self.assertFalse(data['range']['cycle'])
        for start_time, end_time in (('2026-09-29T13:02', '2026-09-29T13:01'), ('2026-09-29T13:01', None)):
            with self.assertRaises(ValueError):
                self.report(start_time=start_time, end_time=end_time)

    def test_append_duplicates_model_switch_and_repeated_scan(self):
        a = usage('2026-09-29T10:01:00Z',10,90,5,reasoning=2)
        b = usage('2026-09-29T10:02:00Z',20,180,10)
        b['payload']['info']['total_token_usage'] = plus(a['payload']['info']['total_token_usage'],b['payload']['info']['last_token_usage'])
        self.write('a.jsonl',[meta('a'),context('gpt-6-astra'),a,a])
        self.index.scan()
        self.assertEqual(self.report()['summary']['total'],105)
        self.write('a.jsonl',[context(),b,b],True)
        self.index.scan()
        self.assertEqual(self.report()['summary']['total'],315)
        self.assertEqual(self.report()['summary']['calls'],2)
        self.assertEqual(self.report()['summary']['reasoning'],2)
        self.assertEqual(len(self.report()['models']),2)
        self.index.scan()
        self.assertEqual(self.report()['summary']['total'],315)

    def test_partial_utf8_record_is_retried(self):
        path = self.write('p.jsonl',[meta('p'),context()])
        event=usage('2026-09-29T10:01:00Z',7,30,3)
        event['extra']='кириллица'
        raw=(json.dumps(event,ensure_ascii=False)+'\n').encode()
        cut=raw.index('ки'.encode())+1
        with path.open('ab') as stream: stream.write(raw[:cut])
        self.index.scan()
        self.assertEqual(self.report()['summary']['total'],0)
        with path.open('ab') as stream: stream.write(raw[cut:])
        self.index.scan()
        self.assertEqual(self.report()['summary']['total'],40)

    def test_inherited_baseline_and_copied_precreation_events(self):
        old=usage('2026-09-28T11:00:00Z',1000,1000,1000)
        new=usage('2026-09-29T10:01:00Z',10,100,5)
        new['payload']['info']['total_token_usage']=plus(old['payload']['info']['total_token_usage'],new['payload']['info']['last_token_usage'])
        self.write('f.jsonl',[meta('f'),context(),old,new])
        self.index.scan()
        self.assertEqual(self.report()['summary']['total'],115)
        self.write('g.jsonl',[meta('g'),context(),new])
        self.index.scan()
        self.assertEqual(self.report()['summary']['total'],230)

    def test_reset(self):
        self.write('r.jsonl',[meta('r'),context(),usage('2026-09-29T10:01:00Z',10,90,5),usage('2026-09-29T10:02:00Z',1,9,2)])
        self.index.scan()
        self.assertEqual(self.report()['summary']['total'],117)
        self.assertTrue(self.report()['diagnostics'])

    def test_dates_moscow_grouped_subagents_and_filters(self):
        self.write('a.jsonl',[meta('a','2026-09-28T10:00:00Z'),context(),usage('2026-09-28T21:01:00Z',10,90,5)])
        self.write('b.jsonl',[meta('b',parent='a'),context('gpt-6-astra'),usage('2026-09-29T10:01:00Z',1,9,2)])
        self.index.scan()
        result=self.report()
        self.assertEqual(result['summary']['total'],117)
        self.assertEqual({r['thread'] for r in result['chats']},{'a'})
        self.assertEqual(sum(r['subagent_calls'] for r in result['chats']),1)
        self.assertEqual({r['thread'] for r in self.report(False)['chats']},{'a','b'})
        self.assertEqual(self.report(model='gpt-6-astra')['summary']['total'],12)
        self.assertEqual(self.report(selected_project='sample-project')['summary']['total'],117)
        self.assertEqual(self.report(selected_project='anime')['summary']['total'],0)
        self.assertEqual(self.report(start='2026-09-28',end='2026-09-28')['summary']['total'],0)

    def test_copied_archive_and_truncation(self):
        events=[meta('a'),context(),usage('2026-09-29T10:01:00Z',10,90,5)]
        self.write('a.jsonl',events)
        self.write('copy.jsonl',events)
        self.index.scan()
        self.assertEqual(self.report()['summary']['total'],105)
        self.write('a.jsonl',[meta('a'),context()])
        self.index.scan()
        self.assertEqual(self.report()['summary']['total'],105)

    def test_missing_model_or_tariff_is_not_zero_cost(self):
        self.write('x.jsonl',[meta('x'),usage('2026-09-29T10:01:00Z',10,90,5)])
        self.index.scan()
        result=self.report()
        self.assertEqual(result['models'][0]['model'],'unknown')
        self.assertIsNone(result['models'][0]['estimated_credits'])
        self.assertEqual(result['pricing']['priced_tokens'],0)
        self.assertEqual(result['summary']['total'],105)

    def test_credit_formula_and_bad_counters(self):
        self.write('a.jsonl',[meta('a'),context(),usage('2026-09-29T10:01:00Z',1_000_000,1_000_000,1_000_000)])
        self.index.scan()
        result=self.report()
        self.assertEqual(result['models'][0]['estimated_credits'],302.5)
        self.assertEqual(result['pricing']['astra_same_tokens'],1525)
        bad=usage('2026-09-29T10:02:00Z',1,9,2)
        bad['payload']['info']['last_token_usage']['cached_input_tokens']=100
        self.write('a.jsonl',[bad],True)
        self.index.scan()
        self.assertEqual(self.report()['summary']['total'],3_000_000)

    def test_csv_formula_title_and_invalid_range(self):
        self.assertIn("'=HYPERLINK", csv_text([dict(title='=HYPERLINK("x")',total=1)]))
        with self.assertRaises(ValueError): self.report(start='2026-09-30',end='2026-09-29')

    def test_http_filtered_export_and_host_check(self):
        self.write('a.jsonl',[meta('a'),context(),usage('2026-09-29T10:01:00Z',10,90,5)])
        self.index.scan()
        server=LocalHTTPServer(('127.0.0.1',0),Handler)
        server.index=self.index
        port=server.server_port
        server.allowed_hosts={f'127.0.0.1:{port}'}
        worker=threading.Thread(target=server.serve_forever,daemon=True)
        worker.start()
        base=f'http://127.0.0.1:{port}'
        try:
            with urllib.request.urlopen(base+'/api/usage?from=2026-09-29&to=2026-09-29&project=sample-project') as response:
                data=json.load(response)
            self.assertEqual(data['summary']['total'],105)
            with urllib.request.urlopen(base+'/api/export?from=2026-09-29&to=2026-09-29&table=models') as response:
                exported=response.read().decode('utf-8-sig')
            self.assertIn('gpt-6.1-sol',exported)
            self.assertIn('105',exported)
            wrong=urllib.request.Request(base+'/api/usage',headers={'Host':'external.example'})
            with self.assertRaises(urllib.error.HTTPError) as caught: urllib.request.urlopen(wrong)
            self.assertEqual(caught.exception.code,403)
        finally:
            server.shutdown()
            server.server_close()
            worker.join()

    def test_token_curve_deduplication_models_boundaries_and_buckets(self):
        first = int(time.time())-3600
        stamp = lambda seconds: datetime.fromtimestamp(first+seconds, timezone.utc).isoformat()
        a = usage(stamp(10),10,90,5,reasoning=2)
        self.write('a.jsonl',[meta('a',created=stamp(-100)),context(),a,a])
        self.write('copy.jsonl',[meta('a',created=stamp(-100)),context(),a])
        self.write('b.jsonl',[meta('b',created=stamp(-100),parent='a'),context('gpt-6-astra'),usage(stamp(20),1,9,2)])
        self.index.scan()
        curve = self.index.token_curve(first,first+3600)
        self.assertEqual(curve['points'][0]['total'],0)
        self.assertEqual(curve['points'][-1]['total'],117)
        self.assertEqual(curve['points'][-1]['models'],{'gpt-6.1-sol':105,'gpt-6-astra':12})
        self.assertEqual(curve['points'][-1]['timestamp'],first+3600)
        self.assertEqual(self.index.token_curve(first+30,first+3600)['points'],[])
        self.assertEqual(self.index.token_curve(first+10,first+20)['points'][-1]['total'],117)
        # Over 400 occupied buckets still conserve all totals in a bounded response.
        con=self.index.connect()
        with con:
            for i in range(1000):
                con.execute('INSERT INTO events(file,offset,timestamp,model,total,event_key) VALUES (?,?,?,?,?,?)',
                    ('synthetic',i,first+i*3.6,'unknown',3,'synthetic-'+str(i)))
        curve=self.index.token_curve(first,first+3600)
        self.assertLessEqual(len(curve['points']),402)
        self.assertEqual(curve['points'][-1]['total'],3117)
        self.assertTrue(all(p['total']==sum(p['models'].values()) for p in curve['points']))

    def test_curve_intervals_compression_resets_and_invalid_range(self):
        now=time.time()
        def point(age,used,reset=1):
            return dict(timestamp=now-age,used_percent=used,reset_at=reset)
        points=[point(31*86400,9),point(8*86400,4),point(2*86400,6),
                point(4*3600,7),point(3000,8),point(2400,8),point(1800,8),
                point(1200,9),point(600,0,2),point(60,1,2)]
        self.index.quota_cache=dict(curve=points)
        server=LocalHTTPServer(('127.0.0.1',0),Handler)
        server.index=self.index
        server.allowed_hosts={f'127.0.0.1:{server.server_port}'}
        worker=threading.Thread(target=server.serve_forever,daemon=True)
        worker.start()
        base=f'http://127.0.0.1:{server.server_port}'
        try:
            for hours in [1,5,24,168,720]:
                with urllib.request.urlopen(base+f'/api/curve?hours={hours}&project=ignored&model=ignored') as response:
                    data=json.load(response)
                self.assertAlmostEqual(data['final_time']-data['first_time'],hours*3600)
                self.assertEqual(data['tokens'],dict(points=[],models=[]))
                self.assertTrue(all(data['first_time']<=p['timestamp']<=data['final_time'] for p in data['curve']))
                self.assertNotIn(points[5],data['curve'])
                self.assertIn(points[4],data['curve'])
                self.assertIn(points[6],data['curve'])
                self.assertIn(points[8],data['curve'])
                self.assertEqual(data['curve'][-1],points[-1])
            first, final = now-2500, now-1000
            with urllib.request.urlopen(base+f'/api/curve?first_time={first}&final_time={final}') as response:
                custom = json.load(response)
            self.assertEqual(custom['first_time'], first)
            self.assertEqual(custom['final_time'], final)
            self.assertEqual(custom['curve'], [points[5], points[6], points[7]])
            for query in ['first_time=1', 'first_time=2&final_time=1', 'first_time=nan&final_time=2', 'first_time=0&final_time=inf']:
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    urllib.request.urlopen(base+'/api/curve?'+query)
                self.assertEqual(caught.exception.code,400)
            for hours in ['2','bad']:
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    urllib.request.urlopen(base+f'/api/curve?hours={hours}')
                self.assertEqual(caught.exception.code,400)
            self.index.quota_cache=None
            with urllib.request.urlopen(base+'/api/curve') as response:
                self.assertEqual(json.load(response)['curve'],[])
        finally:
            server.shutdown();server.server_close();worker.join()

if __name__ == '__main__': unittest.main()

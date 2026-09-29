import unittest
import sqlite3
from quota import build_quota, period_observation
from monitor import RATES
import test_monitor as fixtures
from test_monitor import meta,context,usage

RESET=604800+100
def sample(t,used,reset=RESET):
    return dict(timestamp=t,used_percent=used,reset_at=reset,limit_id='codex',plan='prolite')
def event(key,t,fresh=1,model='gpt-6.1-sol'):
    return dict(event_key=key,timestamp=t,fresh=fresh,cached=0,output=0,
                thread=key,model=model,effort='medium',total=fresh)

class QuotaTests(unittest.TestCase):
    def test_plateau_keeps_early_work_and_conserves_growth(self):
        q=build_quota([sample(100,0),sample(110,0),sample(120,0),sample(140,1)],
            [event('a',105),event('b',115),event('c',130)],RATES)
        self.assertEqual(set(q['allocations']),{'a','b','c'})
        self.assertAlmostEqual(sum(q['allocations'].values()),1)
        self.assertAlmostEqual(q['allocations']['a'],1/3)
        self.assertTrue(q['blocks'][0]['preliminary'])

    def test_parallel_weighted_split_and_baseline_not_distributed(self):
        q=build_quota([sample(100,3),sample(130,7)],[event('a',110),event('b',120,3)],RATES)
        self.assertEqual(q['windows'][0]['baseline_pp'],3)
        self.assertAlmostEqual(q['allocations']['a'],1)
        self.assertAlmostEqual(q['allocations']['b'],3)
        self.assertAlmostEqual(sum(q['allocations'].values()),4)

    def test_unknown_model_or_no_tokens_unassigned(self):
        for events in ([],[event('a',110,model='unknown')]):
            q=build_quota([sample(100,0),sample(130,4)],events,RATES)
            self.assertFalse(q['allocations'])
            self.assertEqual(q['blocks'][0]['unassigned_pp'],4)

    def test_decrease_not_recharged_or_allocated(self):
        q=build_quota([sample(100,2),sample(110,4),sample(120,1),sample(130,4)],
            [event('a',105),event('b',115)],RATES)
        self.assertEqual(q['windows'][0]['observed_growth_pp'],2)
        self.assertFalse(q['allocations'])
        self.assertEqual(q['windows'][0]['unassigned_pp'],2)

    def test_short_dip_recovers_without_extra_charge(self):
        q=build_quota([sample(100,4),sample(110,3),sample(120,4),sample(130,5)],
            [event('a',105),event('b',115)],RATES)
        self.assertAlmostEqual(sum(q['allocations'].values()),1)
        self.assertEqual(q['windows'][0]['assumed_stale'],1)
        self.assertEqual(q['windows'][0]['decreases'],0)

    def test_small_but_persistent_dip_stays_unassigned(self):
        q=build_quota([sample(100,2),sample(110,4),sample(120,3),sample(250,4)],
            [event('a',105),event('b',115)],RATES)
        self.assertFalse(q['allocations'])
        self.assertEqual(q['windows'][0]['unassigned_pp'],2)

    def test_period_boundary_during_lag_does_not_count_recovery(self):
        q=build_quota([sample(100,4),sample(110,3),sample(120,4),sample(130,5)],
            [event('a',105),event('b',115)],RATES)
        self.assertEqual(period_observation(q,115,125)['observed_growth_pp'],0)
        self.assertEqual(period_observation(q,115,135)['observed_growth_pp'],1)

    def test_snapshot_duplicates_and_reset_jitter(self):
        samples=[sample(100,0),sample(100,0,RESET+8),sample(130,4,RESET+2)]
        q=build_quota(samples,[event('a',110)],RATES)
        self.assertEqual(len(q['windows']),1)
        self.assertAlmostEqual(sum(q['allocations'].values()),4)

    def test_manual_reset_does_not_overlap_cycles(self):
        # Second cycle begins at 200; a stale first-cycle observation at 210 must be ignored.
        q=build_quota([sample(100,90),sample(190,95),sample(210,95),
                       sample(201,0,RESET+100),sample(230,2,RESET+100)],
            [event('a',180),event('b',205)],RATES)
        self.assertEqual(len(q['windows']),2)
        self.assertAlmostEqual(q['allocations']['a'],5)
        self.assertAlmostEqual(q['allocations']['b'],2)
        self.assertEqual(sum(b['delta_pp'] for b in q['blocks']),7)

class IntegrationQuotaTests(unittest.TestCase):
    setUp=fixtures.MonitorTests.setUp
    tearDown=fixtures.MonitorTests.tearDown
    write=fixtures.MonitorTests.write
    report=fixtures.MonitorTests.report
    def test_real_capture_filter_invariance_and_name_priority(self):
        a=usage('2026-09-29T10:01:00Z',10,0,5)
        a['payload']['rate_limits']=dict(limit_id='codex',primary=dict(window_minutes=10080,used_percent=0,resets_at=1759226400+604800))
        b=usage('2026-09-29T10:02:00Z',30,0,15)
        b['payload']['rate_limits']=dict(limit_id='codex',primary=dict(window_minutes=10080,used_percent=4,resets_at=1759226400+604800))
        self.write('a.jsonl',[meta('a'),context(),a])
        self.write('b.jsonl',[meta('b'),context('gpt-6-astra'),b])
        con=sqlite3.connect(self.home/'state_5.sqlite')
        con.execute('CREATE TABLE threads(id TEXT,title TEXT,name TEXT,cwd TEXT,archived INTEGER)')
        con.execute('INSERT INTO threads VALUES (?,?,?,?,?)',('a','Первый длинный запрос','Имя из десктопа','',0))
        con.commit();con.close()
        self.index.scan()
        result=self.report()
        filtered=self.report(model='gpt-6-astra')
        self.assertEqual(result['quota']['latest']['used_percent'],4)
        self.assertAlmostEqual(result['summary']['quota_pp'],4)
        self.assertAlmostEqual(filtered['summary']['quota_pp'],4)
        self.assertEqual(next(r['title'] for r in result['chats'] if r['thread']=='a'),'Имя из десктопа')
        self.assertAlmostEqual(sum(r['quota_pp'] for r in result['models']),result['summary']['quota_pp'])
        self.assertAlmostEqual(sum(r['quota_pp'] for r in result['chats']),result['summary']['quota_pp'])

if __name__=='__main__':unittest.main()

import unittest
import sqlite3
from token_tracker.quota import build_quota, period_observation, consumption_pace
from token_tracker.common import RATES
from tests import test_monitor as fixtures
from tests.test_monitor import meta,context,usage

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

class PaceTests(unittest.TestCase):
    def pace(self, samples, now=None):
        return consumption_pace(build_quota(samples, [], RATES),
                                samples[-1]['timestamp'] if now is None else now)

    def test_constant_rate_duplicates_and_sampling_density(self):
        sparse=[sample(t,10+t/600) for t in range(0,3601,600)]
        dense=[sample(t,10+t/600) for t in range(0,3601,60)]
        for rows in (sparse, dense, sparse+sparse):
            pace=self.pace(rows,3600)
            self.assertEqual(pace['status'],'ok')
            self.assertAlmostEqual(pace['pp_per_hour'],6)
            self.assertAlmostEqual(pace['eta_seconds'],84/6*3600)

    def test_time_average_includes_bursts_and_pauses(self):
        steady=[sample(t,10+t/600) for t in range(0,3601,600)]
        faster=[sample(t,10+t/600+max(0,t-1800)/600) for t in range(0,3601,600)]
        self.assertGreater(self.pace(faster)['pp_per_hour'],self.pace(steady)['pp_per_hour'])
        paused=steady+[sample(4200,16),sample(4800,16)]
        self.assertLess(self.pace(paused)['pp_per_hour'],6)
        paused += [sample(t,16) for t in (5400,6000,6600)]
        self.assertEqual(self.pace(paused)['status'],'ok')
        self.assertAlmostEqual(self.pace(paused)['pp_per_hour'],6/6600*3600)

    def test_rounding_short_history_and_stale_are_not_zero(self):
        cases=[([sample(0,10)],0,'insufficient'),
               ([sample(0,10),sample(60,15)],60,'insufficient'),
               ([sample(0,10),sample(900,11)],900,'below_resolution'),
               ([sample(0,10),sample(900,10)],900,'below_resolution'),
               ([sample(0,10),sample(900,15)],1801,'ok')]
        for rows,now,status in cases:
            with self.subTest(status=status):
                pace=self.pace(rows,now)
                self.assertEqual(pace['status'],status)
                if status=='ok':
                    self.assertAlmostEqual(pace['pp_per_hour'],20)
                    self.assertEqual(pace['forecast_status'],'stale')
                else:
                    self.assertIsNone(pace['pp_per_hour'])
                self.assertIsNone(pace['eta_seconds'])

    def test_gaps_resets_and_decreases_preserve_earlier_valid_history(self):
        old=[sample(0,10),sample(900,15),sample(1800,20)]
        for tail in ([sample(4000,40)], [sample(1900,1)],
                     [sample(1900,1,RESET+3600)]):
            pace=self.pace(old+tail)
            self.assertEqual(pace['status'],'ok')
            self.assertAlmostEqual(pace['pp_per_hour'],20)
        recovered=old+[sample(1810,19),sample(1820,20),sample(2400,22)]
        self.assertEqual(self.pace(recovered)['status'],'ok')

    def test_reset_eta_and_exhausted(self):
        rows=[sample(0,10,3600),sample(900,15,3600)]
        self.assertTrue(self.pace(rows)['reset_before_exhaustion'])
        self.assertEqual(self.pace(rows,3600)['forecast_status'],'reset_due')
        pace=self.pace([sample(0,95),sample(900,100)])
        self.assertEqual(pace['forecast_status'],'exhausted')
        self.assertEqual(pace['eta_seconds'],0)

    def test_lookback_excludes_old_work(self):
        rows=[sample(t,10+min(t,1800)/600) for t in range(0,14401,600)]
        self.assertEqual(self.pace(rows)['status'],'below_resolution')
        self.assertEqual(self.pace(rows)['span_seconds'],10800)

    def test_selected_range_changes_average_and_clips_boundaries(self):
        rows=[sample(t,10+t/1800+max(0,t-14400)/300) for t in range(0,18001,600)]
        quota=build_quota(rows,[],RATES)
        hour=consumption_pace(quota,18000,14400,18000)
        five=consumption_pace(quota,18000,0,18000)
        self.assertAlmostEqual(hour['pp_per_hour'],14)
        self.assertAlmostEqual(five['pp_per_hour'],4.4)
        clipped=consumption_pace(quota,18000,14550,17850)
        self.assertAlmostEqual(clipped['pp_per_hour'],14)
        self.assertEqual(clipped['span_seconds'],3300)
        self.assertEqual(clipped['coverage_percent'],100)

    def test_peak_timing_and_snapshot_density_do_not_change_average(self):
        for peak in (600,1800,3000):
            for step in (60,600):
                rows=[sample(t,10+(6 if t>=peak else 0)) for t in range(0,3601,step)]
                pace=consumption_pace(build_quota(rows,[],RATES),3600,0,3600)
                self.assertEqual(pace['status'],'ok')
                self.assertAlmostEqual(pace['pp_per_hour'],6)

    def test_gaps_and_resets_exclude_unknown_time_but_keep_valid_segments(self):
        rows=[sample(0,10),sample(900,13),sample(4500,30),sample(5400,33),
              sample(5500,0,RESET+604800),sample(6400,3,RESET+604800)]
        pace=consumption_pace(build_quota(rows,[],RATES),6400,0,6400)
        self.assertAlmostEqual(pace['pp_per_hour'],12)
        self.assertEqual(pace['growth_pp'],9)
        self.assertEqual(pace['span_seconds'],2700)
        self.assertAlmostEqual(pace['coverage_percent'],2700/6400*100)

    def test_historical_average_and_missing_coverage(self):
        quota=build_quota([sample(0,10),sample(900,13),sample(1800,16)],[],RATES)
        pace=consumption_pace(quota,10000,0,900)
        self.assertAlmostEqual(pace['pp_per_hour'],12)
        self.assertEqual(pace['forecast_status'],'stale')
        self.assertIsNone(pace['eta_seconds'])
        missing=consumption_pace(quota,10000,5000,10000)
        self.assertEqual(missing['status'],'insufficient')
        self.assertIsNone(missing['pp_per_hour'])
        self.assertEqual(missing['coverage_percent'],0)

    def test_conflicting_readings_are_not_integrated(self):
        quota=dict(latest=sample(2700,19),curve=[sample(0,10),sample(900,13),
                   sample(900,15),sample(1800,16),sample(2700,19)])
        pace=consumption_pace(quota,2700,0,2700)
        self.assertEqual(pace['span_seconds'],900)
        self.assertAlmostEqual(pace['pp_per_hour'],12)

    def test_persistent_dip_recovery_is_not_new_consumption(self):
        quota=build_quota([sample(0,10),sample(900,15),sample(1800,20),
                          sample(2000,18),sample(2600,19),sample(3200,21)],[],RATES)
        pace=consumption_pace(quota,3200,0,3200)
        self.assertEqual(pace['growth_pp'],11)
        self.assertEqual(pace['span_seconds'],3000)

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
        self.assertEqual(result['quota']['pace']['range_seconds'],
                         result['range']['final_time']-result['range']['first_time'])
        for key in ('status','pp_per_hour','eta_seconds','span_seconds','growth_pp'):
            self.assertEqual(result['quota']['pace'][key],filtered['quota']['pace'][key])
        self.assertEqual(result['quota']['latest']['used_percent'],4)
        self.assertAlmostEqual(result['summary']['quota_pp'],4)
        self.assertAlmostEqual(filtered['summary']['quota_pp'],4)
        self.assertEqual(next(r['title'] for r in result['chats'] if r['thread']=='a'),'Имя из десктопа')
        self.assertAlmostEqual(sum(r['quota_pp'] for r in result['models']),result['summary']['quota_pp'])
        self.assertAlmostEqual(sum(r['quota_pp'] for r in result['chats']),result['summary']['quota_pp'])

if __name__=='__main__':unittest.main()

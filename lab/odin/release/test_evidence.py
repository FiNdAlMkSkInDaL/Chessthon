"""Lightweight tamper/incomplete-evidence tests, without importing an engine."""
from copy import deepcopy
from dataclasses import asdict
import io
import unittest

import chess
import chess.pgn

from lab.odin.release.plan import bind_lane,lane_plans,validate_plan
from lab.odin.release.validate_match import audit,apply_criterion
from lab.odin.release.native_gate import dispatch_search


def fixture(fen='8/8/8/8/8/k7/2q5/K7 b - - 0 300',uci='c2a2'):
    plan = {'schema_version':1,'base_ms':120000,'increment_ms':500,
            'init_budget_s':90.,'ply_cap':600,'packages':{'chess':'1.11.2'},
            'source_provenance':{'official/harness/referee.py':'d'*64},'suites':{'primary':{
            'candidate_sha256':'a'*64,'baseline_sha256':'b'*64,'openings_sha256':'c'*64,
            'openings':[fen],'min_pairs':1,'threshold':0.,
            'lanes':[{'id':'a','cpu':0,'opening_indices':[0]}]}}}
    suite = plan['suites']['primary']
    declared = [asdict(p) for p in lane_plans(suite,'a')]
    start = {key:plan[key] for key in ('base_ms','increment_ms','init_budget_s','ply_cap','source_provenance')}
    from lab.odin.release.validate_match import THREADS
    start.update(type='run_start',run_id='test-run',lane='a',suite='primary',cpu=0,
                 plan_sha256='e'*64,openings_sha256='c'*64,official_referee_unchanged=True,
                 official_runner_unchanged=True,ready_override=False,runner_shim=None,
                 service_runtime_limit_s=900,
                 thread_env={name:'1' for name in THREADS},pairs_planned=1,plans=declared,
                 runtime={'python':'3.12.13','machine':'x86_64','platform':'Linux-test',
                          'packages':plan['packages'],'cpu_models':['test']})
    for role in ('candidate','baseline'):
        start[role] = {'sha256':suite[role+'_sha256'],'private_snapshot_verified':True,
                       'entries':[{'name':'agent.py','sha256':'f'*64}]}
    rows = [start]
    for gp in declared:
        board = chess.Board(fen)
        board.push_uci(uci)
        terminal = board.outcome(claim_draw=True)
        result = ('draw' if terminal.winner is None else 'white' if terminal.winner else 'black') if terminal else 'draw'
        termination = terminal.termination.name.lower() if terminal else 'ply_cap'
        pgn = chess.pgn.Game.from_board(board)
        pgn.headers.update(Result={'white':'1-0','black':'0-1','draw':'1/2-1/2'}[result],Termination=termination)
        cc = 'white' if gp['white_role']=='candidate' else 'black'
        game = dict(gp,type='game',run_id='test-run',result=result,termination=termination,pgn=str(pgn),
                    candidate_colour=cc,candidate_points=.5 if result=='draw' else float(result==cc),
                    candidate_failure=False,baseline_failure=False,candidate_sha256='a'*64,
                    baseline_sha256='b'*64,extraction_errors={'white':[],'black':[]})
        for colour in ('white','black'):
            role = gp[colour+'_role']
            game[colour+'_sha256'] = suite[role+'_sha256']
            moves = [] if colour=='white' else [{'ok':True,'request':1,'fen':fen,'move':uci,
                                                 'elapsed_ms':1.,'time_left_ms':120000}]
            sample = {'MemoryMax':str(2*1024**3),'MemorySwapMax':'0','TasksMax':'128','NoNewPrivileges':'yes',
                      'LimitFSIZE':'268435456','RestrictAddressFamilies':'AF_UNIX','ActiveState':'active',
                      'query_returncode':0,'CPUAffinity':'0','MainPID':'123','CPUQuotaPerSecUSec':'1s',
                      'RuntimeMaxUSec':'15min'}
            game[colour+'_timing'] = {'role':role,'cpu':0,'envelope_errors':[],'cleanup_error':None,
                  'init_s':30.,'memory_peak_bytes':400000000,'moves':moves,'move_count':len(moves),
                  'unit':f'test-{gp["game"]}-{colour}',
                  'memory_samples':[dict(sample,phase='after_init'),dict(sample,phase='before_stop')]}
        rows.append(game)
    rows.append({'type':'run_summary','run_id':'test-run','games_completed':2,'pairs_completed':1,
                 'planned_games':2,'protocol_failures':0})
    return plan,rows


class EvidenceTests(unittest.TestCase):
    def check(self,plan,rows):
        return audit(plan,'e'*64,'primary',[('fixture',rows)],bootstrap_samples=100)

    def test_mate_before_absolute_cap_replays(self):
        plan,rows = fixture()
        result = self.check(plan,rows)
        self.assertTrue(result['evidence_valid'],result['failure_reasons'])
        self.assertEqual(result['verdict'],'PASS')
        self.assertEqual(result['plies_replayed'],2)

    def test_absolute_cap_draw_replays_from_midgame_fen(self):
        plan,rows = fixture('7k/7p/8/8/8/8/P7/K7 b - - 0 300','h8g8')
        self.assertTrue(self.check(plan,rows)['evidence_valid'])

    def test_old_300_ply_termination_rejected(self):
        plan,rows = fixture('7k/7p/8/8/8/8/P7/K7 b - - 0 150','h8g8')
        result = self.check(plan,rows)
        self.assertFalse(result['evidence_valid'])
        self.assertTrue(any('no current-referee terminal' in e for e in result['failure_reasons']))

    def test_incomplete_run_rejected(self):
        plan,rows = fixture()
        self.assertFalse(self.check(plan,rows[:-1])['evidence_valid'])

    def test_missing_colour_rejected(self):
        plan,rows = fixture()
        del rows[2]
        self.assertFalse(self.check(plan,rows)['evidence_valid'])

    def test_wrong_candidate_hash_rejected(self):
        plan,rows = fixture()
        rows[1]['candidate_sha256'] = '0'*64
        self.assertFalse(self.check(plan,rows)['evidence_valid'])

    def test_source_and_plan_identity_rejected(self):
        plan,rows = fixture()
        rows[0]['source_provenance'] = {}
        rows[0]['plan_sha256'] = '0'*64
        self.assertFalse(self.check(plan,rows)['evidence_valid'])

    def test_timing_fen_and_overrun_rejected(self):
        plan,rows = fixture()
        rows[1]['black_timing']['moves'][0]['fen'] = chess.STARTING_FEN
        rows[1]['black_timing']['moves'][0]['elapsed_ms'] = 120100
        self.assertFalse(self.check(plan,rows)['evidence_valid'])

    def test_cleanup_and_memory_rejected(self):
        plan,rows = fixture()
        rows[1]['white_timing']['cleanup_error'] = 'still running'
        rows[1]['white_timing']['memory_peak_bytes'] = 2*1024**3+1
        self.assertFalse(self.check(plan,rows)['evidence_valid'])

    def test_reused_service_rejected(self):
        plan,rows = fixture()
        rows[2]['white_timing']['unit'] = rows[1]['white_timing']['unit']
        self.assertFalse(self.check(plan,rows)['evidence_valid'])

    def test_plan_binding_checks_exact_inputs(self):
        plan,_ = fixture()
        suite = plan['suites']['primary']
        self.assertEqual(len(bind_lane(plan,'primary','a',0,suite['openings'],'c'*64,'a'*64,'b'*64,120000,500)),2)
        with self.assertRaises(ValueError):
            bind_lane(plan,'primary','a',0,suite['openings'],'c'*64,'0'*64,'b'*64,120000,500)
        with self.assertRaises(ValueError):
            bind_lane(plan,'primary','a',1,suite['openings'],'c'*64,'a'*64,'b'*64,120000,500)

    def test_duplicate_plan_coverage_rejected(self):
        plan,_ = fixture()
        plan['suites']['primary']['lanes'].append({'id':'b','cpu':1,'opening_indices':[0]})
        with self.assertRaises(ValueError):
            validate_plan(plan)

    def test_guard_uses_raw_score_with_ci_retained(self):
        stats = {'verdict':'FAIL','reasons':['lower confidence bound below threshold'],
                 'gate':{'threshold':.5},'validation_errors':[],'candidate_failures':{},
                 'opponent_failures':{},'included_pairs':16,'score':.5625,
                 'bootstrap':{'score_ci':[.40,.70]}}
        result = apply_criterion(stats,{'criterion':'raw_score','threshold':.5,'min_pairs':16})
        self.assertEqual(result['verdict'],'PASS')
        self.assertEqual(result['bootstrap']['score_ci'],[.40,.70])
        self.assertEqual(result['paired_ci_gate_diagnostic']['verdict'],'FAIL')

    def test_guard_rejects_equal_score_and_missing_pairs(self):
        stats = {'verdict':'FAIL','reasons':[],'gate':{},'validation_errors':[],
                 'candidate_failures':{},'opponent_failures':{},'included_pairs':15,'score':.5}
        result = apply_criterion(stats,{'criterion':'raw_score','threshold':.5,'min_pairs':16})
        self.assertEqual(result['verdict'],'FAIL')
        self.assertEqual(len(result['reasons']),2)

    def test_odin_signature_dispatch(self):
        class Core:
            @staticmethod
            def search_root(pos,packed_root,hard_ms,soft_ms,game_zkeys,absolute_ply=0):
                return game_zkeys,absolute_ply
        self.assertEqual(dispatch_search(Core,None,[],10,0,[123],418),([123],418))

    def test_original_and_control_signature_dispatch(self):
        class Position:
            fullmove,side = 210,0
        class Core:
            @staticmethod
            def search_root(pos,packed_root,hard_ms,soft_ms,adjudicate,game_zkeys):
                return adjudicate,game_zkeys
        self.assertEqual(dispatch_search(Core,Position(),[],10,0,[123],418),(False,[123]))
        with self.assertRaises(ValueError):
            dispatch_search(Core,Position(),[],10,0,[123],419)


if __name__=='__main__':
    unittest.main()

"""Small synthetic-evidence tests; no chess engine or external process runs."""
import copy
import unittest

import chess
import chess.pgn

from lab.storm.validate_holdout import (
    HASHES, MEMORY_LIMIT_BYTES, PACKAGES, SOURCE_FILES, THREAD_ENV,
    audit, validate_game, validate_metadata,
)

SOURCES = {name:'0'*64 for name in SOURCE_FILES}
OPENINGS_HASH = '1'*64
FENS = ['7k/8/5KQ1/8/8/8/8/8 w - - 0 '+str(index+1) for index in range(200)]


def start_record(run_id='test-a', offset=160):
    cpu = 0 if offset == 160 else 1
    plans = []
    for index in range(offset,offset+10):
        for leg in (0,1):
            plans.append({'game':len(plans)+1, 'pair':index-offset+1,
                          'opening_index':index, 'fen':FENS[index],
                          'white_role':'candidate' if leg==0 else 'baseline',
                          'black_role':'baseline' if leg==0 else 'candidate',
                          'white_cpu':cpu, 'black_cpu':cpu})
    return {'type':'run_start','run_id':run_id,'base_ms':120000,'increment_ms':500,
            'init_budget_s':90.0,'ply_cap':300,'pairs_planned':10,'cpu':cpu,'plans':plans,
            'official_referee_unchanged':True,'official_runner_unchanged':True,
            'ready_override':False,'runner_shim':None,'openings_sha256':OPENINGS_HASH,
            'source_provenance':SOURCES, 'thread_env':{name:'1' for name in THREAD_ENV},
            'runtime':{'python':'3.12.3','machine':'x86_64','platform':'Linux-test',
                       'packages':PACKAGES,'cpu_models':['Test CPU']},
            **{role:{'sha256':digest,'private_snapshot_verified':True,
                     'entries':[{'name':'agent.py','sha256':'2'*64}]} for role,digest in HASHES.items()}}


def game_record(start, plan):
    board = chess.Board(plan['fen'])
    board.push_uci('g6g7')
    assert board.is_checkmate()
    pgn = chess.pgn.Game.from_board(board)
    pgn.headers.update(Result='1-0',Termination='checkmate')
    result = {'type':'game','run_id':start['run_id'],**plan,
              'candidate_sha256':HASHES['candidate'],'baseline_sha256':HASHES['baseline'],
              'candidate_colour':'white' if plan['white_role']=='candidate' else 'black',
              'candidate_failure':False,'baseline_failure':False,
              'extraction_errors':{'white':[],'black':[]},'pgn':str(pgn),
              'result':'white','termination':'checkmate',
              'candidate_points':float(plan['white_role']=='candidate')}
    properties = {'query_returncode':0,'ActiveState':'active','MainPID':'123',
                  'CPUAffinity':str(start['cpu']),'MemoryMax':str(MEMORY_LIMIT_BYTES),'MemorySwapMax':'0',
                  'TasksMax':'128','NoNewPrivileges':'yes','LimitFSIZE':'268435456',
                  'RestrictAddressFamilies':'AF_UNIX','CPUQuotaPerSecUSec':'1s','RuntimeMaxUSec':'10min'}
    for colour in ('white','black'):
        role = plan[colour+'_role']
        moves = [{'request':1,'fen':chess.Board(plan['fen']).fen(),'move':'g6g7','ok':True,
                  'time_left_ms':120000,'elapsed_ms':10.0}] if colour=='white' else []
        result[colour+'_sha256'] = HASHES[role]
        result[colour+'_timing'] = {'role':role,'cpu':start['cpu'],'init_s':1.0,
                                    'envelope_errors':[],'cleanup_error':None,'memory_peak_bytes':100000,
                                    'memory_samples':[dict(properties,phase=phase) for phase in ('after_init','before_stop')],
                                    'moves':moves,'move_count':len(moves),
                                    'unit':f'{start["run_id"]}-{plan["game"]}-{colour}'}
    return result


def completed_logs():
    logs = []
    for label,offset in [('test-a',160),('test-b',170)]:
        start = start_record(label,offset)
        games = [game_record(start,plan) for plan in start['plans']]
        end = {'type':'run_summary','run_id':label,'games_completed':20,'pairs_completed':10,
               'planned_games':20,'protocol_failures':0}
        logs.append((label,[start,*games,end]))
    return logs


class HoldoutAuditTests(unittest.TestCase):
    def test_valid_metadata_passes(self):
        errors = []
        validate_metadata(start_record(),'test',SOURCES,OPENINGS_HASH,errors)
        self.assertEqual(errors,[])

    def test_short_screen_time_control_is_rejected(self):
        start = start_record()
        start.update(base_ms=10000,increment_ms=100)
        errors = []
        validate_metadata(start,'test',SOURCES,OPENINGS_HASH,errors)
        self.assertTrue(any('base_ms' in e for e in errors))
        self.assertTrue(any('increment_ms' in e for e in errors))

    def test_different_zip_cannot_be_pooled(self):
        start = start_record()
        start['candidate']['sha256'] = 'f'*64
        errors = []
        validate_metadata(start,'test',SOURCES,OPENINGS_HASH,errors)
        self.assertTrue(any('candidate ZIP hash' in e for e in errors))

    def test_partial_runs_fail_as_incomplete(self):
        logs = [('a',[start_record('a',160)]),('b',[start_record('b',170)])]
        result = audit(logs,SOURCES,FENS,OPENINGS_HASH,bootstrap_samples=100)
        self.assertEqual(result['verdict'],'FAIL')
        self.assertFalse(result['evidence_valid'])
        self.assertTrue(any('incomplete' in reason for reason in result['failure_reasons']))

    def test_complete_legal_evidence_does_not_bypass_statistical_gate(self):
        # Each pair has a White win and a White win after swapping candidate
        # colour: 50% candidate score. Evidence is valid, promotion must fail.
        result = audit(completed_logs(),SOURCES,FENS,OPENINGS_HASH,bootstrap_samples=100)
        self.assertTrue(result['evidence_valid'],result['failure_reasons'])
        self.assertEqual(result['games_replayed'],40)
        self.assertEqual(result['statistics']['included_pairs'],20)
        self.assertEqual(result['statistics']['score'],.5)
        self.assertEqual(result['verdict'],'FAIL')

    def test_pgn_and_logged_uci_must_agree(self):
        start = start_record()
        game = game_record(start,start['plans'][0])
        game['white_timing']['moves'][0]['move'] = 'g6g8'
        errors = []
        validate_game(game,start,start['plans'][0],errors)
        self.assertTrue(any('FEN/UCI' in e for e in errors))

    def test_integrity_errors_block_even_complete_results(self):
        logs = completed_logs()
        logs[0][1][1]['white_timing']['cleanup_error'] = 'service still active'
        result = audit(logs,SOURCES,FENS,OPENINGS_HASH,bootstrap_samples=100)
        self.assertFalse(result['evidence_valid'])
        self.assertTrue(any('cleanup' in e for e in result['failure_reasons']))

    def test_concurrent_lanes_cannot_share_cpu(self):
        logs = completed_logs()
        second_start = logs[1][1][0]
        second_start['cpu'] = 0
        for plan in second_start['plans']:
            plan.update(white_cpu=0, black_cpu=0)
        for game in logs[1][1][1:-1]:
            game.update(white_cpu=0, black_cpu=0)
            for colour in ('white','black'):
                timing = game[colour+'_timing']
                timing['cpu'] = 0
                for sample in timing['memory_samples']:
                    sample['CPUAffinity'] = '0'
        result = audit(logs,SOURCES,FENS,OPENINGS_HASH,bootstrap_samples=100)
        self.assertFalse(result['evidence_valid'])
        integrity_reasons = [reason for reason in result['failure_reasons']
                             if not reason.startswith('Statistical gate:')]
        self.assertEqual(integrity_reasons,['Concurrent lanes must use distinct CPU IDs'])


if __name__=='__main__':
    unittest.main()

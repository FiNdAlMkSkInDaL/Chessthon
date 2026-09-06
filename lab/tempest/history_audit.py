"""Old match terminal replay under new source; never relabel the old match."""
import json,io,collections,hashlib,ast
from pathlib import Path
import chess,chess.pgn
from rule_probe import current
H=Path(__file__).resolve().parent;R=H.parents[1]
def key(b):return ' '.join(b.fen().split()[:4])
def main():
    rows=[];known=set();starts=set();nplies=0
    for p in (R/'lab/odin/native_release/odin-v6-architecture-r1/overnight112').glob('primary-?.jsonl'):
        for line in p.open():
            r=json.loads(line)
            if 'pgn' not in r:continue
            g=chess.pgn.read_game(io.StringIO(r['pgn']));b=g.board();starts.add(key(b));low=0
            for m in g.mainline_moves():known.add(key(b));low+=len(b.piece_map())<=4;b.push(m);nplies+=1
            known.add(key(b));rows.append(dict(run_id=r['run_id'],game=r['game'],old_termination=r['termination'],current_at_old_end=current(b),final_fen=b.fen(),low_material_plies=low,pgn_sha256=hashlib.sha256(r['pgn'].encode()).hexdigest()))
    for name in ('Chess_results_day1','chess_results_day2','Chess_results_day3'):
        for p in (R/name).glob('*.pgn'):
            g=chess.pgn.read_game(io.StringIO(p.read_text(encoding='utf-8-sig')))
            if not g:continue
            b=g.board();starts.add(key(b))
            for m in g.mainline_moves():known.add(key(b));b.push(m)
            known.add(key(b))
    cases=json.loads((H/'corpus-v1.json').read_text());reserved=[dict(id=c['id'],group=c['group'],position_previously_used=key(chess.Board(c['fen'])) in known,start_previously_used=key(chess.Board(c['start_fen'])) in starts) for c in cases if c['split']=='confirmation']
    result=dict(games=len(rows),plies=nplies,old_terminations=dict(collections.Counter(r['old_termination'] for r in rows)),current_at_old_end=dict(collections.Counter(str(r['current_at_old_end']) for r in rows)),old_draws_continuing_now=sum(r['old_termination'] in ('threefold_repetition','fifty_moves') and r['current_at_old_end'] is None for r in rows),games_with_4_or_fewer=sum(r['low_material_plies']>0 for r in rows),rows=rows,reserved_audit=reserved,reserved_scope='These are unsearched in Tempest, not certified fresh promotion families. Exact historical positions and start FENs audited against 112-game match and supplied site games. Other old development/training family overlap still requires exclusion. Do not use as a release holdout.')
    (H/'history-audit.json').write_text(json.dumps(result,indent=2))
    identity={'archive_sha256':hashlib.sha256((R.parent/'agent.zip').read_bytes()).hexdigest(),'odin_v6_source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (R/'odin_v6').glob('*.py')},'prototype_baseline_ast_identical':all(ast.dump(ast.parse(p.read_text()))==ast.dump(ast.parse((H/'prototypes/baseline'/p.name).read_text())) for p in (R/'odin_v6').glob('*.py')),'baseline_core_line_ending_normalization':True,'own_game_inventory':{name:[p.name for p in (R/name).glob('*.pgn')] for name in ('Chess_results_day1','chess_results_day2','Chess_results_day3')}}
    (H/'identity.json').write_text(json.dumps(identity,indent=2));print({k:v for k,v in result.items() if k not in ('rows','reserved_audit')})
if __name__=='__main__':main()

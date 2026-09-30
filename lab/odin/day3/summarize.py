"""Bind Day3 review data, site telemetry and exact-source critical-root probes."""
import hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
import chess,chess.pgn
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
games=[]
for p in sorted((ROOT/'Chess_results_day3').glob('*.pgn')):
    with p.open(encoding='utf-8-sig') as f:g=chess.pgn.read_game(f)
    assert g and not g.errors
    b=g.board();own=g.headers['White']=='Finlay Phillips';clocks=[]
    for n in g.mainline():
        assert b.outcome(claim_draw=True) is None and b.ply()<600 and n.move in b.legal_moves
        if b.turn==own and n.clock() is not None:clocks.append(n.clock())
        b.push(n.move)
    outcome=b.outcome(claim_draw=True);assert outcome and outcome.result()==g.headers['Result']
    assert outcome.termination.name.lower()==g.headers['Termination']
    log=p.with_suffix('.log');text=log.read_text()
    games.append({'round':int(g.headers['Round']),'opponent':g.headers['Black' if own else 'White'],'colour':'white' if own else 'black','points':.5 if outcome.winner is None else float(outcome.winner==own),
                  'result':outcome.result(),'termination':outcome.termination.name,'plies':len(b.move_stack),'init_s':float(re.search(r'Ready in\s+([\d.]+)',text)[1]),
                  'final_clock_s':clocks[-1],'min_clock_after_increment_s':min(clocks),'pgn_sha256':sha(p),'log_sha256':sha(log)})
probes={};metadata={}
for version,source in [(5,'odin_submission'),(6,'odin_v6')]:
    rows=[json.loads(s) for s in (HERE/f'v{version}-probes.jsonl').read_text().splitlines()]
    assert rows[-1]['verdict']=='PASS' and rows[-1]['probes']==16
    assert rows[0]['source_sha256']=={p.name:sha(p) for p in (ROOT/source).glob('*.py')}
    metadata[str(version)]=rows[0];probes[version]={(r['id'],r['mode']):r for r in rows if r['type']=='probe'}
deep=[json.loads(s) for s in (HERE/'deep-reference.jsonl').read_text().splitlines()];assert len(deep)==8
comparisons=[]
for r in deep:
    row={k:r[k] for k in ('id','round','ply','move_number','played_san','best_own_cp','played_own_cp','loss_cp','time_left_ms')}
    row['reference_best_san']=r['best']['pv_san'][0]
    for version in (5,6):
        row[f'v{version}']={mode:{'move':probes[version][r['id'],mode]['san'],'depth':probes[version][r['id'],mode]['info']['depth'],'score':probes[version][r['id'],mode]['info']['score']} for mode in ('adaptive','fixed-3000ms')}
    comparisons.append(row)
report={'source_version_at_receipt':'the signer archive (not in git) was verified as Odin v5 c7d8972e...e21102; user says these games came from that submission. Site exports do not independently embed an archive SHA.',
        'day3_games':games,'wins':sum(g['points']==1 for g in games),'draws':sum(g['points']==.5 for g in games),'losses':sum(g['points']==0 for g in games),'reference_positions':sum(1 for p in (HERE/'reference').glob('*.jsonl') for s in p.read_text().splitlines() if json.loads(s)['type']=='position'),
        'critical_comparisons':comparisons,'same_adaptive_choices':sum(r['v5']['adaptive']['move']==r['v6']['adaptive']['move'] for r in comparisons),'probe_metadata':metadata,
        'limitations':'Finite Stockfish reference, selected diagnostics, absent historical engine TT, signer hardware differs from site. Same historical served-position information reconstructed; no future moves exposed. Neither site records nor these probes enter the112-game strength estimate. Small opening-dependent Day3 sample cannot rank versions.',
        'pipeline_note':'Initial generalized review run failed before writing metadata due to a relative-path conversion; empty initial files/error logs preserved. Corrected runs under reference/ completed all positions.'}
(HERE/'review-summary.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ('critical_comparisons','probe_metadata','day3_games')}))

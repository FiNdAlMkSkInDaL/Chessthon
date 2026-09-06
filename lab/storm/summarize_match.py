"""Compact actual-game outcomes/clock/telemetry; never substitutes for Elo gate."""
import argparse
import json
from pathlib import Path
import statistics as stats

import chess


def summarize(paths):
    rows=[]
    for path in paths:
        for line in Path(path).read_text(encoding='utf-8').splitlines():
            if line.strip(): rows.append(json.loads(line))
    starts={r['run_id']:r for r in rows if r.get('type')=='run_start'}
    games=[r for r in rows if r.get('type')=='game']
    scores=[r['candidate_points'] for r in games if r['candidate_points'] is not None]
    report={'games':len(games),'wins':scores.count(1.0),'draws':scores.count(0.5),
            'losses':scores.count(0.0),'score':stats.mean(scores) if scores else None,
            'candidate_failures':sum(bool(r['candidate_failure']) for r in games),
            'baseline_failures':sum(bool(r['baseline_failure']) for r in games),
            'candidate_hashes':sorted({r['candidate_sha256'] for r in games}),
            'baseline_hashes':sorted({r['baseline_sha256'] for r in games}),
            'opening_indices':sorted({r['opening_index'] for r in games})}
    for role in ('candidate','baseline'):
        clocks=[]; totals=[]; first20=[]; depths=[]; memory=[]; inits=[]; maxmove=[]
        phases={name:[] for name in ('high_material','middle_material','low_material')}
        decisions={name:[] for name in ('1-20','21-40','41-60','61+')}
        forced=[]
        for game in games:
            colour='white' if game['white_role']==role else 'black'
            timing=game[colour+'_timing']; moves=timing['moves']
            inc=starts[game['run_id']]['increment_ms']
            if moves:
                clocks.append((moves[-1]['time_left_ms']-moves[-1]['elapsed_ms']+inc)/1000)
                totals.append(sum(m['elapsed_ms'] for m in moves)/1000)
                maxmove.append(max(m['elapsed_ms'] for m in moves)/1000)
            if len(moves)>=20:first20.append(sum(m['elapsed_ms'] for m in moves[:20])/1000)
            for index, move in enumerate(moves):
                board=chess.Board(move['fen'])
                phase=sum(len(board.pieces(piece,colour))*weight
                          for piece,weight in ((chess.KNIGHT,1),(chess.BISHOP,1),
                                               (chess.ROOK,2),(chess.QUEEN,4))
                          for colour in chess.COLORS)
                phase_name='high_material' if phase>=18 else 'middle_material' if phase>=8 else 'low_material'
                phases[phase_name].append(move['elapsed_ms']/1000)
                decision_name='1-20' if index<20 else '21-40' if index<40 else '41-60' if index<60 else '61+'
                decisions[decision_name].append(move['elapsed_ms']/1000)
                if board.legal_moves.count()==1:forced.append(move['elapsed_ms']/1000)
            depths.extend(t['depth'] for t in timing.get('s4_telemetry',[]))
            if timing.get('memory_peak_bytes'):memory.append(timing['memory_peak_bytes']/1024**2)
            if timing.get('init_s') is not None:inits.append(timing['init_s'])
        report[role]={'mean_clock_left_s':stats.mean(clocks) if clocks else None,
                      'mean_thinking_s':stats.mean(totals) if totals else None,
                      'first20_mean_s':stats.mean(first20) if first20 else None,
                      'first20_stddev_s':stats.pstdev(first20) if first20 else None,
                      'mean_completed_depth':stats.mean(depths) if depths else None,
                      'max_move_s':max(maxmove,default=None),'max_init_s':max(inits,default=None),
                      'max_memory_mib':max(memory,default=None),
                      'phase_thinking_s':{name:{'moves':len(values),'mean_s':stats.mean(values) if values else None}
                                          for name,values in phases.items()},
                      'decision_thinking_s':{name:{'moves':len(values),'mean_s':stats.mean(values) if values else None}
                                             for name,values in decisions.items()},
                      'forced_reply_count':len(forced),'forced_reply_total_s':sum(forced)}
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('logs',nargs='+'); p.add_argument('--out',type=Path)
    a=p.parse_args(); result=summarize(a.logs); text=json.dumps(result,indent=2)+'\n'
    if a.out:a.out.write_text(text,encoding='utf-8')
    print(text,end='')

"""Build history-complete Odin development cases; not submission lookup data."""
import json,hashlib
from pathlib import Path
import chess

def read(path):return [json.loads(s) for s in path.read_text(encoding='utf-8-sig').splitlines()]

def main():
    home=Path('lab/odin')
    deep=read(home/'reference-deep.jsonl');confirmed=read(home/'reference-confirmed.jsonl')
    conversion=read(home/'reference-conversion-confirmed.jsonl')
    confirmed += conversion
    existing={(r['game_id'],r['ply']) for r in deep if r['type']=='position'}
    for r in conversion:
        if r['type']=='confirmation' and (r['game_id'],r['ply']) not in existing:
            d=dict(r,type='position')
            d.update(r['unrestricted']['last_exact_matching_bestmove'])
            d['conversion_only']=True
            deep.append(d)
    conf={(r['game_id'],r['ply']):r for r in confirmed if r['type']=='confirmation'}
    out=[]
    for r in deep:
        if r['type']!='position':continue
        b=chess.Board(r['start_fen'])
        for u in r['history_uci']:b.push_uci(u)
        assert b.fen()==r['fen'] and b.outcome(claim_draw=True) is None
        c={k:r[k] for k in ('game_id','ply','start_fen','history_uci','fen','storm_colour','played_uci','played_san','move_number','source','source_sha256')}
        c.update(id=r['game_id']+f'-ply{r["ply"]}',kind='game_diagnostic',label_status='Finite-budget offline reference lead; do not hardcode one expected UCI or ship this data.')
        if not r.get('conversion_only'):
            c['reference_2m_exploratory']={k:r[k] for k in ('white_cp','white_mate','pv_uci','pv_san','depth')}
        d=conf.get((r['game_id'],r['ply']))
        if d:
            assert d['played']['final_bestmove']==r['played_uci']
            a=d['unrestricted']['last_exact_matching_bestmove'];z=d['played']['last_exact_matching_bestmove']
            assert a is not None and z is not None
            assert not a['lowerbound'] and not a['upperbound'] and not z['lowerbound'] and not z['upperbound']
            c['reference_5m']={'best':a,'played_root':z,'source':'lab/odin/reference-conversion-confirmed.jsonl' if r['game_id'].startswith('holdout') else 'lab/odin/reference-confirmed.jsonl'}
        if r['game_id']=='holdout-a-g12-o165' and r['move_number']==61:
            c['excluded_reference']='The attempted Kg8-only alternative returned a PV starting Ke7; invalid, excluded.'
        if r['game_id']=='holdout-a-g12-o165' and r['move_number']==83:
            tb=json.loads((home/'tablebase-opening165-move83.json').read_text(encoding='utf-8-sig'))['result']
            c['tablebase']={'root_category':tb['category'],'drawing_moves':[m['uci'] for m in tb['moves'] if m['category']=='draw'],'played_child_category':next(m['category'] for m in tb['moves'] if m['uci']==r['played_uci']),'source':'lab/odin/tablebase-opening165-move83.json','note':'Child categories are child-side-to-move perspective; tablebase does not encode prior repetition.'}
        out.append(c)
    repro=json.loads((home/'code_review_repro.json').read_text())
    for c in repro['see']:
        b=chess.Board(c['fen']);m=chess.Move.from_uci(c['move']);assert m in b.legal_moves
        b.push(m);assert not [x for x in b.legal_moves if x.to_square==m.to_square and b.is_capture(x)]
        out.append({'id':'see-'+c['kind'],'kind':'exact_legal_exchange_fixture','fen':c['fen'],'move_uci':c['move'],'expected_see_cp':100,'old_see_cp':c['source_isolated_see'],'source':'lab/odin/code_review_repro.json'})
    assert len(out)==39
    meta={'type':'metadata','cases':len(out),'note':'Odin development diagnostics; reviewed cases are not a fresh holdout or runtime move database.','source_hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (home/'reference-deep.jsonl',home/'reference-confirmed.jsonl',home/'reference-conversion-confirmed.jsonl',home/'code_review_repro.json',home/'tablebase-opening165-move83.json')}}
    (home/'odin-diagnostics.jsonl').write_text('\n'.join(json.dumps(r,allow_nan=False) for r in [meta]+out)+'\n')
    print('ODIN DIAGNOSTICS PASS',len(out),'cases; 15 streamed confirmations; invalid Kg8 alternative excluded')

if __name__=='__main__':main()

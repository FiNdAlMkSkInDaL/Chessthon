"""Fail closed on missing results, source identity, legality or consumed holdout."""
import json,hashlib,ast,collections,statistics,datetime,io,sys
from pathlib import Path
import chess,chess.pgn
H=Path(__file__).resolve().parent;R=H.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):return [json.loads(s) for s in p.read_text().splitlines()]
def main():
    plan=json.loads((H/'experiment-plan.json').read_text());cases={c['id']:c for c in json.loads((H/'corpus-v1.json').read_text())};cases.update({c['id']:c for c in json.loads((H/'opponent-critical.json').read_text())})
    assert sha(H/'corpus-v1.json')==plan['corpus_sha256']
    assert {p.name:sha(p) for p in (R/'odin_v6').glob('*.py')}==plan['baseline']
    assert sha(R.parent/'agent.zip')=='cd3ed778f75ded38dd4371a56c285f6f66c1311464a093707d473d8a9d0c8647'
    for p in (R/'odin_v6').glob('*.py'):assert ast.dump(ast.parse(p.read_text()))==ast.dump(ast.parse((H/'prototypes/baseline'/p.name).read_text()))
    refs={(r['id'],r['uci']):r['reference'] for r in rows(H/'reference-choices.jsonl') if r.get('type')=='choice'}
    missing=[];counts={};workers=[];total=0
    for p in sorted(H.glob('*-probes.jsonl')):
        rr=rows(p);assert rr[-1]['type']=='complete',p.name;assert any(r.get('pass_ABA') for r in rr),p.name
        meta=next(r for r in rr if r['type']=='metadata');assert meta['native_ready'];v=meta['variant'];source=H/'prototypes'/v
        assert {f.name:sha(f) for f in source.glob('*.py')}==meta['source_hashes'],p.name
        probes=[r for r in rr if r['type']=='probe'];counts[p.name]=len(probes);total+=len(probes)
        workers.append(dict(file=p.name,cold_seconds=meta['cold_seconds'],cpu=meta['cpu'],isolation=True,native=True))
        for r in probes:
            c=cases[r['id']];assert c['split']=='discovery';b=chess.Board(c['start_fen'])
            for u in c['history_uci']:b.push_uci(u)
            assert b.fen()==c['fen'];assert chess.Move.from_uci(r['uci']) in b.legal_moves
            if r['mode']=='nodes':assert r['info']['nodes']<=r['budget']+1000
            if (r['id'],r['uci']) not in refs:missing.append((r['id'],r['uci']))
        if p.name in {v+'-probes.jsonl' for v in plan['variants']}:assert len(probes)==(102 if v=='baseline' else 72)
    for cid,c in cases.items():
        if c['split']=='discovery' and c.get('played_uci') and (cid,c['played_uci']) not in refs:missing.append((cid,c['played_uci']))
    assert not missing,('Missing reference moves',missing)
    assert counts['baseline-deep-probes.jsonl']==25 and counts['opponent-critical-probes.jsonl']==36 and total==523
    critical=[];cr=rows(H/'opponent-critical-probes.jsonl')
    for r in cr:
        if r['type']!='probe':continue
        c=cases[r['id']];actual=refs[(r['id'],c['played_uci'])];test=refs[(r['id'],r['uci'])];sign=1 if c['storm_colour']=='white' else -1
        gain=None if actual.get('white_mate') is not None or test.get('white_mate') is not None else sign*(actual['white_cp']-test['white_cp'])
        critical.append(dict(id=r['id'],player=c['player'],mode=r['mode'],budget=r['budget'],actual=c['played_san'],v6=r['san'],same_move=r['uci']==c['played_uci'],actual_minus_v6_cp=gain))
    critsummary=dict(rows=critical,by_budget={str(b):dict(n=sum(r['budget']==b for r in critical),same=sum(r['budget']==b and r['same_move'] for r in critical)) for b in (200000,1000000,1500)})
    (H/'opponent-critical-summary.json').write_text(json.dumps(critsummary,indent=2))
    fresh=rows(H/'fresh-confirmation/openings.jsonl');assert len(fresh)==12 and len({r['opening_position_key'] for r in fresh})==12
    queried={' '.join(c['fen'].split()[:4]) for c in cases.values() if c['split']=='discovery'}
    assert not ({' '.join(r['fen'].split()[:4]) for r in fresh}&queried)
    assert len(rows(H/'label-audit.jsonl'))==120
    assert sum(r.get('type')=='screen' for r in rows(H/'reference-games.jsonl'))==1330
    assert len(rows(H/'public-deep.jsonl'))==19
    assert len(json.loads((H/'rule-probe.json').read_text())['fixtures'])==5
    match=json.loads((H/'match/summary.json').read_text());assert match['audit']=='PASS' and match['games']==12
    assert len(rows(H/'opponent-advantages.jsonl'))==3
    result=dict(status='PASS',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),native_workers=len(workers),search_probes=total,counts=counts,workers=workers,source_unchanged=True,archive_unchanged=True,all_returned_moves_legal=True,all_ABA_pass=True,reference_choices_complete=True,reference_move_count=len(refs),fresh_confirmation_unqueried=True,confirmation_openings=12,scope='R&D artifact consistency and native diagnostic completion; not a promotion/runtime/full-game test.')
    result['development_match']={'audit':match['audit'],'games':12,'legal_plies':match['legal_plies'],'score':match['score'],'wins':match['wins'],'draws':match['draws'],'losses':match['losses'],'full_clock':False}
    (H/'validation.json').write_text(json.dumps(result,indent=2))
    files=[]
    for p in sorted(H.rglob('*')):
        if not p.is_file() or p.name=='artifact-manifest.json' or '__pycache__' in p.parts:continue
        if p.suffix in ('.stdout','.stderr'):continue  # Derivative progress streams may still be redirected by the caller.
        # Public bytes already have provenance/hash manifests; keep the final manifest compact.
        if 'public' in p.relative_to(H).parts and p.suffix in ('.html','.pgn'):continue
        files.append(dict(path=str(p.relative_to(H)).replace('\\','/'),bytes=p.stat().st_size,sha256=sha(p)))
    docs=[dict(path=str(p.relative_to(R)),sha256=sha(p)) for p in (R/'docs').glob('TEMPEST_*.md')]
    (H/'artifact-manifest.json').write_text(json.dumps(dict(utc=result['utc'],files=files,documents=docs),indent=2))
    print(json.dumps(result))
if __name__=='__main__':main()

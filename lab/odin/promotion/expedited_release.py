"""User-authorized practical release after16 games, without claiming the112 gate.

Preserves the original plan/logs and uses the same native, source, per-game
replay, clock/resource and atomic-copy validators. The user changed the sample
after14 observed games; statistical estimates are descriptive, not a passed
predeclared confidence test. Default dry-run; --apply copies exact tested bytes.
"""
import argparse
from dataclasses import asdict
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from lab.odin.promotion.promote import inspect_archive,validate_gate,validate_desktop,apply_bytes,need
from lab.odin.release.plan import digest,lane_plans,source_provenance,validate_plan
from lab.odin.release.validate_match import read_log,validate_metadata,validate_game
from lab.paired_match_stats import analyze_rows

STAGE=ROOT/'lab/odin/native_release/odin-release-r10'
FINAL=STAGE/'final112'
OUT=ROOT/'lab/odin/promotion/reports/expedited-r10'
CANDIDATE='c7d8972e823eb821c016010445d4b02996daff954d870d63083c445850e21102'
PLAN='26551be568a8e2fc7eaeb60530fd2c3934c86c8056021c7db840e7414c686734'
CONTROL='35c6a33fed2e81acead145de53639ce516b1d24a6701a89a8c5fff81a582baf1'

def collect():
    raw=(STAGE/'candidate-linux-x86.zip').read_bytes()
    manifest=inspect_archive(raw,ROOT/'odin_submission')
    need(manifest['sha256']==CANDIDATE,'Unexpected candidate')
    need(digest(FINAL/'plan.json')==PLAN,'Original plan changed')
    plan=json.loads((FINAL/'plan.json').read_text(encoding='utf-8'))
    validate_plan(plan)
    need(plan['suites']['primary']['baseline_sha256']==CONTROL,'Unexpected control')
    need(plan['source_provenance']==source_provenance(ROOT,ROOT/'lab/odin/official-harness-91f70e54'),'Frozen tools changed')
    native=validate_gate(json.loads((STAGE/'native-gate.json').read_text(encoding='utf-8')),manifest,plan)
    supplemental=json.loads((STAGE/'supplemental.json').read_text(encoding='utf-8'))
    state=json.loads((STAGE/'state-gate.json').read_text(encoding='utf-8'))
    need(supplemental['verdict']=='PASS' and supplemental['total_fifty_cases']==15,'Supplemental failure')
    need(state['status']=='PASS' and state['positions']==3857 and state['native_make_undo_edges']==9503,'State gate failure')
    stops=[json.loads(s) for s in (STAGE/'user-directed-stop.log').read_text(encoding='utf-8').splitlines()]
    need(stops[0]['event']=='USER_DIRECTED_SAMPLE_CHANGE','Missing user-directed stop record')
    need({r.get('lane'):r.get('complete_games') for r in stops if r.get('event')=='PAIR_BOUNDARY_STOP_REQUESTED'}=={'a':8,'b':8},'Both pair boundaries were not recorded')
    games=[];replays=[];errors=[];starts=[];loghashes={}
    for lane in ('a','b'):
        path=FINAL/f'primary-{lane}.jsonl'
        loghashes[path.name]=digest(path)
        rows,parse_errors=read_log(path);errors.extend(parse_errors)
        need(digest(path)==loghashes[path.name],'Log changed during reading')
        ss=[r for r in rows if r.get('type')=='run_start']
        need(len(ss)==1,'Expected one run start')
        start=ss[0];starts.append(start)
        need(start['lane']==lane and start['cpu']=={'a':0,'b':1}[lane],'Lane identity differs')
        validate_metadata(start,plan,'primary',PLAN,errors)
        declared=[asdict(r) for r in lane_plans(plan['suites']['primary'],lane)]
        need(start['plans']==declared,'Original full plan differs')
        need(start['candidate']['entries']==manifest['entries'],'Source manifest differs')
        need(all(r.get('run_id')==start['run_id'] for r in rows),'Run identities differ')
        gs=[r for r in rows if r.get('type')=='game']
        need([g['game'] for g in gs]==list(range(1,9)),'Expected exactly four complete pairs per lane')
        interruptions=[r for r in rows if r.get('type')=='run_error']
        need(len(interruptions)==1 and interruptions[0]['games_completed']==8 and interruptions[0]['error'].startswith('KeyboardInterrupt:'),'Unexpected controller termination')
        need(not any(r.get('type')=='run_summary' for r in rows),'Do not relabel interrupted80-game run as completed')
        for game in gs:
            replay=validate_game(game,start,declared[game['game']-1],plan['suites']['primary'],errors)
            if replay:replays.append(replay)
        games.extend(gs)
    need(not errors,'Evidence errors: '+'; '.join(errors))
    need(len(replays)==16,'Not all games replayed')
    need(len({s['run_id'] for s in starts})==2,'Run identity reused')
    need(starts[0]['baseline']['entries']==starts[1]['baseline']['entries'],'Baseline manifests differ')
    units=[u for r in replays for u in r['units']]
    need(len(set(units))==32 and None not in units,'Agent service reused')
    stats=analyze_rows(games,source='user-directed16-game-prefix',bootstrap_samples=10000,min_pairs=8,threshold=.5)
    need(stats['validation_errors']==[] and not stats['candidate_failures'] and not stats['opponent_failures'],'Statistical input validation failed')
    need(stats['wins']+stats['draws']+stats['losses']==16 and stats['included_pairs']==8 and stats['excluded_failure_pairs']==0,'Paired coverage mismatch')
    need(stats['score']>.5,'Practical release requires a positive complete-pair result')
    report={'verdict':'PASS','mode':'dry-run','name':'Odin v5','validated_utc':datetime.now(timezone.utc).isoformat(),
            'decision_kind':'User-authorized expedited practical release; not a passed predeclared confidence gate',
            'policy_change':'User rejected5–6 more hours and the112-game gate after14 games were observed. Finish the current color pairs, audit all16 games, retain cold Linux reliability gates, and decide without claiming statistical proof.',
            'original_112_game_plan_completed':False,'original_storm_32_game_guard_completed':False,
            'confidence_gate_claimed':False,'candidate':manifest,'canonical_source':str((ROOT/'odin_submission').resolve()),
            'original_plan_sha256':PLAN,'operational':native,'supplemental':supplemental,'state_gate':state,
            'complete_pairs':8,'games_replayed':16,'plies_replayed':sum(r['plies'] for r in replays),
            'statistics_descriptive_only':stats,'match_log_sha256':loghashes,
            'baseline':'Minimal current-rules Storm control; original Storm is preserved, but its planned separate guard was cancelled.',
            'preserved_desktop_hashes':validate_desktop(ROOT.parent,CANDIDATE),'promotion_tool_sha256':digest(Path(__file__))}
    return raw,report

def write(report):
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'odin-release.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    s=report['statistics_descriptive_only']
    text=(f"# Odin v5 — expedited release\n\nStatus: **{report['mode']}**. Exact Linux ZIP SHA-256: `{CANDIDATE}`.\n\n"
          f"Full-clock current-rules Storm comparison: **{s['wins']} wins,{s['draws']} draws,{s['losses']} losses; {s['score']:.1%} of points** across8 complete color pairs. "
          f"All16 games ({report['plies_replayed']} plies) passed legal replay, clock, source identity and resource checks. Zero operational failures.\n\n"
          "The exact archive passed cold Linux import/protocol/perft/deadline gates,15 fifty-clock cases and3,857-state/9,503-edge checks. "
          "Its40 additional Windows game-position probes are diagnostic only.\n\n"
          "The user explicitly prioritized rapid iteration and ended the112-game plan after the current pairs. "
          "This is a practical release decision from promising evidence, **not a passed95% confidence gate**. "
          "The separate32-game original-Storm guard was cancelled. Original plans and interrupted logs are preserved without alteration. "
          "The magnitude of the strength gain and leaderboard impact remain uncertain.\n\n"
          "Desktop outputs, when applied: `agent.zip` and `Odin-v5.zip`. Original `Storm-v4.zip` and `v3-agent.zip` remain preserved. No site upload performed.\n")
    (OUT/'ODIN_RELEASE_REPORT.md').write_text(text,encoding='utf-8')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    raw,report=collect()
    if args.apply:
        need(inspect_archive(raw,ROOT/'odin_submission')==report['candidate'],'Source changed')
        apply_bytes(raw,report,ROOT.parent)
    write(report)
    print(json.dumps({'verdict':report['verdict'],'mode':report['mode'],'score':report['statistics_descriptive_only']['score'],'sha256':CANDIDATE,'report':str(OUT/'ODIN_RELEASE_REPORT.md')}))

if __name__=='__main__':main()

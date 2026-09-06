"""Validate all final evidence, then optionally promote the exact tested ZIP.

Dry run is the default. This utility never builds/repackages an archive, runs
an engine, changes frozen match helpers, or uploads to the competition.
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime,timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path
import stat
import tempfile
import zipfile

import chess

from lab.odin.release.plan import source_provenance,validate_plan
from lab.odin.release.validate_match import audit,read_log

ROOT=Path(__file__).resolve().parents[3]
STORM_SHA='15db92a79feff24cf52f5b85974f55504753f981823d7e6d92881fb62812e85c'
V3_SHA='3397e7a8ca55696bb8d7586a9c73cbeabc0c8b6f51b26cdc8c26562a37c91408'
PINNED=ROOT/'lab/odin/official-harness-91f70e54'
PACKAGES={'chess':'1.11.2','numpy':'2.5.2','numba':'0.67.0','llvmlite':'0.49.0'}
MEMORY=2*1024**3


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def need(condition,message):
    if not condition:
        raise ValueError(message)


def finite(value):
    return type(value) in (int,float) and math.isfinite(value)


def inspect_archive(raw,source):
    """Audit bytes once, and require identical canonical readable source files."""
    source=Path(source).resolve()
    need(source.is_dir(),'Canonical source directory is missing')
    entries=[]
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos=archive.infolist()
        names=[i.filename for i in infos]
        need(bool(names) and len(names)==len(set(names)),'Empty or duplicate ZIP members')
        need(names.count('agent.py')==1,'Expected exactly one root agent.py')
        need(sum(i.file_size for i in infos)<50_000_000,'Uncompressed source must be below50MB')
        for info in infos:
            name=info.filename
            need(not info.is_dir() and '/' not in name and '\\' not in name and
                 Path(name).name==name and name.endswith('.py') and name not in ('chess.py','types.py'),
                 'Expected flat Python source only: '+repr(name))
            need(info.create_system==3,'ZIP member lacks native Unix creation metadata: '+name)
            need(not stat.S_ISLNK(info.external_attr>>16) and not info.flag_bits&1,
                 'Symlink/encrypted ZIP member: '+name)
            payload=archive.read(info)
            text=payload.decode('utf-8-sig')
            ast.parse(text,filename=name)
            local=source/name
            need(local.is_file() and not local.is_symlink() and local.read_bytes()==payload,
                 'Canonical source differs from tested ZIP: '+name)
            entries.append({'name':name,'sha256':sha(payload),'compressed_bytes':info.compress_size,
                            'uncompressed_bytes':len(payload)})
    actual={p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file()
            and not ('__pycache__' in p.relative_to(source).parts and p.suffix=='.pyc')}
    need(actual==set(names),'Canonical source has extra/missing non-cache files')
    return {'sha256':sha(raw),'zip_bytes':len(raw),'uncompressed_bytes':sum(e['uncompressed_bytes'] for e in entries),
            'entry_count':len(entries),'entries':sorted(entries,key=lambda e:e['name'])}


def validate_contract(plan,candidate_sha):
    validate_plan(plan)
    need(set(plan['suites'])=={'primary','guard'},'Expected exactly primary and guard suites')
    need(plan['packages']==PACKAGES,'Frozen plan package versions differ from competition runtime')
    for name,pairs,criterion in [('primary',40,'paired_ci_lower'),('guard',16,'raw_score')]:
        suite=plan['suites'][name]
        need(suite['candidate_sha256']==candidate_sha,name+': candidate hash differs from exact ZIP')
        need(len(suite['openings'])==pairs and suite['min_pairs']==pairs,name+': wrong required complete pair count')
        need(suite.get('criterion','paired_ci_lower')==criterion and suite['threshold']==.5,
             name+': promotion criterion differs from prescribed decision')
    need(plan['suites']['guard']['baseline_sha256']==STORM_SHA,'Guard baseline must be original released Storm')
    control=plan['suites']['primary']['baseline_sha256']
    need(control not in (candidate_sha,STORM_SHA,V3_SHA),'Primary baseline must be the separate rules-corrected Storm control')


def validate_resource(service,cpu,label):
    need(service.get('role')=='candidate' and service.get('cpu')==cpu,label+': wrong role/CPU')
    need(service.get('envelope_errors')==[] and 'cleanup_error' in service and service['cleanup_error'] is None,
         label+': missing/failed envelope or cleanup')
    peak=service.get('memory_peak_bytes')
    need(type(peak) is int and 0<peak<=MEMORY,label+': missing/over-limit memory peak')
    samples=service.get('memory_samples',[])
    need(len(samples)==2 and {s.get('phase') for s in samples}=={'after_init','before_stop'},label+': resource samples missing')
    for sample in samples:
        for key,want in [('CPUAffinity',str(cpu)),('MemoryMax',str(MEMORY)),('MemorySwapMax','0'),
                         ('TasksMax','128'),('LimitFSIZE','268435456'),('NoNewPrivileges','yes'),
                         ('RestrictAddressFamilies','AF_UNIX'),('ActiveState','active'),('query_returncode',0)]:
            need(sample.get(key)==want,label+': bad resource '+key)
        need(sample.get('CPUQuotaPerSecUSec') in ('1s','1000000us','1000000'),label+': CPU quota missing')
        need(sample.get('RuntimeMaxUSec') in ('15min','15min 0s','900s','900000000us'),label+': service ceiling differs')
        need(not sample.get('query_error') and int(sample.get('MainPID',0))>0,label+': service query invalid')
    need(bool(service.get('unit')),label+': missing fresh service ID')


def validate_gate(gate,manifest,plan):
    need(gate.get('verdict')=='PASS' and not gate.get('error') and not gate.get('cleanup_errors') and
         not gate.get('preserved_temporary_tree'),'Operational gate failed or has unclean termination')
    need(gate.get('archive',{}).get('sha256')==manifest['sha256'],'Operational gate tested a different ZIP')
    need(gate['archive'].get('private_snapshot_verified') is True,'Operational snapshot is unverified')
    need(sorted(gate['archive'].get('entries',[]),key=lambda e:e['name'])==manifest['entries'],
         'Operational gate source manifest differs from ZIP')
    runtime=gate.get('runtime',{})
    need(str(runtime.get('python','')).startswith('3.12.') and runtime.get('machine')=='x86_64' and
         str(runtime.get('platform','')).startswith('Linux-') and runtime.get('packages')==PACKAGES and
         bool(runtime.get('cpu_models')),'Operational gate lacks required native runtime identity')
    need(gate.get('source_provenance')==plan['source_provenance'],'Operational helper/referee provenance differs from plan')
    need(gate.get('service_runtime_limit_s')==900 and gate.get('odin_rules_required') is True,
         'Operational gate lacks current-rules probes or service limit')
    core=gate.get('structural',{})
    need(core.get('verdict')=='PASS' and core.get('original_numba_ready') is True and
         bool(core.get('nopython_root_signatures')),'Original native ready/signature evidence missing')
    for label,value in [('structural',core.get('cold_agent_import_s')),
                        ('official protocol',gate.get('protocol',{}).get('cold_agent_import_s'))]:
        need(finite(value) and 0<=value<90,label+': import did not satisfy90-second ceiling')
    expected={'startpos':8902,'kiwipete':97862,'cpw3':2812,'cpw4':9467,'cpw5':62379,'cpw6':89890}
    perft=core.get('perft',[])
    need(len(perft)==6 and {r.get('name'):r.get('nodes') for r in perft}==expected and
         all(r.get('depth')==3 for r in perft),'Six native perft checks are missing or wrong')
    probes=core.get('deadline_probes',[])
    need(len(probes)==12,'Expected all12 native deadline probes')
    for probe in probes:
        board=chess.Board(probe['fen'])
        need(board.is_valid() and chess.Move.from_uci(probe['move']) in board.legal_moves,'Native probe move illegal')
        need(probe['hard_ms'] in (30,100,300) and finite(probe.get('elapsed_ms')) and
             0<=probe['elapsed_ms']<probe['hard_ms']+200,'Native deadline probe exceeded budget margin')
    special=core.get('current_rules_and_history_probes',[])
    cap=[r for r in special if 'fen' in r]
    history=[r for r in special if 'history_length' in r]
    need(len(cap)==2 and {r['history_length'] for r in history}>={500,620,750,900},
         'Current cap or long-history probe coverage missing')
    need({r['fen'] for r in cap}=={'7k/7p/8/8/8/8/P7/K7 b - - 0 300',
                                  '8/8/8/8/8/k7/2q5/K7 b - - 0 300'},'Unexpected or duplicate cap fixtures')
    for probe in history:
        need(finite(probe.get('elapsed_ms')) and 0<=probe['elapsed_ms']<300,
             'Long-history deadline probe exceeded margin')
    for probe in cap:
        board=chess.Board(probe['fen'])
        need(board.is_valid() and board.ply()==599,'Invalid cap fixture')
        board.push_uci(probe['move'])
        need((board.is_checkmate() and probe['score']>=31000) or
             (not board.is_checkmate() and board.ply()==600 and probe['score']==0),'Cap/mate precedence probe failed')
    for phase in ('structural','protocol'):
        need(gate.get(phase+'_extraction_errors')==[],phase+': extraction integrity missing')
        validate_resource(gate[phase+'_service'],gate['cpu'],phase)
    need(gate['structural_service']['unit']!=gate['protocol_service']['unit'],'Gate reused one agent service')
    protocol=gate['protocol']
    moves=protocol.get('moves',[])
    need(len(moves)==4 and [r.get('time_left_ms') for r in moves]==[100,450,1000,1000],
         'Official protocol probe coverage differs')
    recorded=gate['protocol_service'].get('moves',[])
    need(len(recorded)==4==gate['protocol_service'].get('move_count'),'Protocol service move count differs')
    for index,(move,record) in enumerate(zip(moves,recorded),1):
        board=chess.Board(move['fen'])
        need(board.is_valid() and chess.Move.from_uci(move['move']) in board.legal_moves,'Official protocol move illegal')
        need(finite(move.get('elapsed_ms')) and 0<=move['elapsed_ms']<move['time_left_ms'],'Official protocol probe flagged')
        need(record.get('ok') is True and record.get('request')==index and
             all(record.get(k)==move[k] for k in ('fen','move','time_left_ms')),'Official protocol request mismatch')
    return {'verdict':'PASS','candidate_sha256':manifest['sha256'],
            'cold_import_s':{'structural':core['cold_agent_import_s'],'protocol':protocol['cold_agent_import_s']},
            'peak_memory_bytes':max(gate[p+'_service']['memory_peak_bytes'] for p in ('structural','protocol'))}


def validate_desktop(desktop,candidate_sha):
    desktop=Path(desktop).resolve()
    need(desktop.is_dir(),'Desktop directory is missing')
    checks={}
    for name,expected in [('Storm-v4.zip',STORM_SHA),('v3-agent.zip',V3_SHA)]:
        path=desktop/name
        need(path.is_file() and not path.is_symlink(),'Required preserved backup is missing: '+name)
        actual=sha(path.read_bytes())
        need(actual==expected,'Preserved backup has unexpected bytes: '+name)
        checks[name]=actual
    for name in ('agent.zip','Odin-v5.zip'):
        path=desktop/name
        if path.exists():
            need(path.is_file() and not path.is_symlink(),'Unsafe release destination: '+name)
            actual=sha(path.read_bytes())
            allowed={candidate_sha,STORM_SHA} if name=='agent.zip' else {candidate_sha}
            need(actual in allowed,'Refusing to replace an unrecognized release: '+name)
            checks[name]=actual
    return checks


def collect(args):
    raw=args.candidate.read_bytes()
    manifest=inspect_archive(raw,args.source)
    plan_raw=args.plan.read_bytes()
    plan=json.loads(plan_raw.decode('utf-8-sig'))
    validate_contract(plan,manifest['sha256'])
    need(plan['source_provenance']==source_provenance(ROOT,PINNED),
         'Local frozen validator/referee/helper source differs from plan')
    gate_raw=args.gate.read_bytes()
    gate=json.loads(gate_raw.decode('utf-8-sig'))
    operation=validate_gate(gate,manifest,plan)
    suites={}
    log_hashes={}
    for name,paths in [('primary',args.primary_logs),('guard',args.guard_logs)]:
        need(len(set(p.resolve() for p in paths))==len(paths),name+': repeated log paths')
        before_hashes={path:sha(path.read_bytes()) for path in paths}
        parsed=[read_log(path) for path in paths]
        need(all(sha(path.read_bytes())==before_hashes[path] for path in paths),name+': log changed while being read')
        need(not any(errors for _,errors in parsed),name+': unreadable/incomplete JSONL evidence')
        result=audit(plan,sha(plan_raw),name,[(str(path.resolve()),rows) for path,(rows,_) in zip(paths,parsed)])
        need(result.get('evidence_valid') is True and result.get('verdict')=='PASS',
             name+' match gate failed: '+'; '.join(result.get('failure_reasons',[])))
        suites[name]=result
        log_hashes[name]={path.name:before_hashes[path] for path in paths}
        need(len(log_hashes[name])==len(paths),name+': ambiguous duplicate log basenames')
    backups=validate_desktop(args.desktop,manifest['sha256'])
    return raw,{'verdict':'PASS','mode':'dry-run','name':'Odin v5',
               'validated_utc':datetime.now(timezone.utc).isoformat(),
               'candidate':manifest,'canonical_source':str(args.source.resolve()),
               'plan_sha256':sha(plan_raw),'operational_gate_sha256':sha(gate_raw),
               'operational':operation,'match_audits':suites,'match_log_sha256':log_hashes,
               'preserved_desktop_hashes':backups,'promotion_tool_sha256':sha(Path(__file__).read_bytes())}


def apply_bytes(raw,report,desktop):
    """Stage both byte-identical outputs, recheck preserved identities, replace."""
    need(report.get('verdict')=='PASS','Cannot apply a failed/unvalidated report')
    digest=sha(raw)
    need(report.get('candidate',{}).get('sha256')==digest,'Validated candidate bytes changed before apply')
    desktop=Path(desktop).resolve()
    validate_desktop(desktop,digest)
    staged=[]
    report['mode']='applying'
    report['applied_outputs']={}
    try:
        for name in ('Odin-v5.zip','agent.zip'):
            fd,filename=tempfile.mkstemp(prefix='.'+name+'.odin-',suffix='.tmp',dir=desktop)
            path=Path(filename)
            with os.fdopen(fd,'wb') as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            need(sha(path.read_bytes())==digest,'Staged output differs from validated bytes')
            staged.append((path,desktop/name))
        validate_desktop(desktop,digest)
        for path,target in staged:
            os.replace(path,target)
            report['applied_outputs'][target.name]=digest
            need(sha(target.read_bytes())==digest,'Copied release hash mismatch: '+target.name)
        report['mode']='applied'
        report['applied_utc']=datetime.now(timezone.utc).isoformat()
        report['desktop_outputs']={target.name:sha(target.read_bytes()) for _,target in staged}
        report['preserved_desktop_hashes']=validate_desktop(desktop,digest)
    finally:
        for path,_ in staged:
            if path.exists():
                path.unlink()


def write_report(report,directory):
    directory.mkdir(parents=True,exist_ok=True)
    (directory/'odin-release.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    if report['verdict']!='PASS':
        prose='Odin promotion validation or copying failed.\n\n'+report['error']+'\n'
        if report.get('applied_outputs'):
            prose+='\nFiles copied before the failure: '+', '.join(report['applied_outputs'])+'.\n'
    else:
        p=report['match_audits']['primary']['statistics']
        g=report['match_audits']['guard']['statistics']
        prose=(f"Odin v5: {report['mode']}.\n\nExact ZIP SHA-256: `{report['candidate']['sha256']}`.\n\n"
               f"Primary: {p['wins']} wins, {p['draws']} draws, {p['losses']} losses; score {p['score']:.1%}; "
               f"paired 95% CI {p['bootstrap']['score_ci']}; all80 games replay-verified.\n\n"
               f"Original-Storm guard: {g['wins']} wins, {g['draws']} draws, {g['losses']} losses; "
               f"score {g['score']:.1%}; all32 games replay-verified. Guard decision uses final raw score above50%.\n\n"
               'Native operational gate, exact canonical source, original Storm/v3 backups and all identity checks passed. '
               'This utility did not upload to the competition.\n')
    (directory/'ODIN_RELEASE_REPORT.md').write_text(prose,encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate',type=Path,required=True)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--gate',type=Path,required=True)
    parser.add_argument('--primary-logs',nargs='+',type=Path,required=True)
    parser.add_argument('--guard-logs',nargs='+',type=Path,required=True)
    parser.add_argument('--desktop',type=Path,default=ROOT.parent)
    parser.add_argument('--report-dir',type=Path,default=Path(__file__).resolve().parent/'reports')
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    report=None
    try:
        raw,report=collect(args)
        if args.apply:
            need(inspect_archive(raw,args.source)==report['candidate'],'Canonical source changed before promotion')
            apply_bytes(raw,report,args.desktop)
        write_report(report,args.report_dir)
        print(json.dumps({'verdict':'PASS','mode':report['mode'],'sha256':report['candidate']['sha256'],
                          'report':str(args.report_dir/'odin-release.json')}),flush=True)
        return 0
    except (ValueError,KeyError,TypeError,OSError,UnicodeError,SyntaxError,zipfile.BadZipFile) as exc:
        failure={'verdict':'FAIL','mode':'not-promoted' if not report or report.get('mode') not in ('applying','applied') else 'apply-failed',
                 'error':type(exc).__name__+': '+str(exc),'utc':datetime.now(timezone.utc).isoformat()}
        if report and report.get('applied_outputs'):
            failure['applied_outputs']=report['applied_outputs']
        write_report(failure,args.report_dir)
        print(json.dumps(failure),flush=True)
        return 1


if __name__=='__main__':
    raise SystemExit(main())

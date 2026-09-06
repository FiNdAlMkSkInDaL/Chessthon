"""Bounded offline quiet-position labels; never agent/runtime code."""
from __future__ import annotations
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import ctypes
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

import chess
import chess.engine

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CORPUS = ROOT / "lab/odin/training/corpus-20k.jsonl"
ENGINE = Path(r"C:\Users\finla\AppData\Local\ChessTK\analysis-tools\stockfish-19\stockfish\stockfish-windows-arm64-universal.exe")
NODES = 100_000
MAX_LEAF_PLY = 12
SEED = "odin-quiet-eval-20260905-v1"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_id(row):
    return f"{row['source_game']}:{row['ply']}"


def prepare():
    rows = [json.loads(line) for line in CORPUS.read_text().splitlines()]
    selected = []
    eligible = Counter()
    for kind, quota in (("middlegame", 2000), ("attack", 2000), ("ending", 2000)):
        pool = []
        for row in rows:
            if row["bucket"] != kind:
                continue
            board = chess.Board(row["fen"])
            if not board.is_valid() or board.is_check() or board.is_game_over(claim_draw=True):
                continue
            copy = dict(row)
            copy["id"] = stable_id(row)
            copy["selection_key"] = hashlib.sha256((SEED + copy["id"]).encode()).hexdigest()
            pool.append(copy)
        eligible[kind] = len(pool)
        selected.extend(sorted(pool, key=lambda r:r["selection_key"])[:quota])
    selected.sort(key=lambda r:r["selection_key"])
    output = HERE/"selection.jsonl"
    output.write_text("".join(json.dumps(r,separators=(",",":"))+"\n" for r in selected),encoding="utf-8")
    plan = {"frozen_utc":datetime.now(timezone.utc).isoformat(), "seed":SEED,
            "selection_rows":len(selected),"selection_sha256":sha(output),"original_corpus_sha256":sha(CORPUS),
            "eligible":dict(eligible), "counts":dict(Counter(r["bucket"]+":"+r["split"] for r in selected)),
            "partition_policy":"Original source-game/first-eight-ply-family train-validation assignment retained exactly; no release-opening source is read.",
            "nodes_per_analysis":NODES,"engine_sha256":sha(ENGINE),"worker_cpus":[5,6,7,8],
            "engine_threads":1,"hash_mb":32,"max_forcing_plies":MAX_LEAF_PLY,"max_analyses_per_row":2,
            "screen":{"score_abs_max_cp":1000,"last_two_exact_score_drift_cp":40,
                      "minimum_exact_score_nodes":10000,"required_leaf":"Not in check; reference best move is neither capture, promotion nor check."},
            "time_limit":"Each worker stops by the shared wall deadline after finishing its current <=100k-node analysis; any unprocessed suffix remains reported, not silently replaced.",
            "fit_plan":{"features":"Same original 11 geometry counts, independently tapered MG/EG; no intercept; actual PeSTO tempo baseline",
                        "huber_cp":100,"ridge_grid":[10,100,1000],"irls_iterations":6,
                        "hyperparameter_selection":"Training-only first-eight-ply-family hash holdout, 20%; final validation never selects regularization.",
                        "bounds":"Sign/range constraints frozen in fit.py before labels are inspected."}}
    (HERE/"plan.json").write_text(json.dumps(plan,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"event":"selection_frozen","rows":len(selected),"counts":plan["counts"]}),flush=True)


def forcing(board, move):
    return board.is_check() or board.is_capture(move) or bool(move.promotion) or board.gives_check(move)


def analyse(engine, board):
    engine.configure({"Clear Hash":None})
    exact = []
    total = 0
    with engine.analysis(board,chess.engine.Limit(nodes=NODES),game=object()) as stream:
        for item in stream:
            total=max(total,item.get("nodes",0))
            if "score" in item and not item.get("lowerbound") and not item.get("upperbound"):
                value=item["score"].white()
                exact.append({"white_cp":value.score(),"mate":value.mate(),"depth":item.get("depth"),
                              "nodes":item.get("nodes",0),"pv":[m.uci() for m in item.get("pv",[])]})
    if not exact:
        return None
    result=dict(exact[-1])
    result["total_nodes"]=total
    result["prior_exact_cp"]=exact[-2]["white_cp"] if len(exact)>1 else None
    return result


def worker(cpu, rows, deadline):
    kernel=ctypes.WinDLL("kernel32",use_last_error=True)
    kernel.GetCurrentProcess.restype=ctypes.c_void_p
    kernel.SetProcessAffinityMask.argtypes=(ctypes.c_void_p,ctypes.c_size_t)
    if not kernel.SetProcessAffinityMask(kernel.GetCurrentProcess(),1<<cpu):
        raise ctypes.WinError(ctypes.get_last_error())
    engine=chess.engine.SimpleEngine.popen_uci(str(ENGINE))
    engine.configure({"Threads":1,"Hash":32})
    file=HERE/f"labels-cpu{cpu}.jsonl"
    counters=Counter()
    started=time.monotonic()
    try:
        with file.open("w",encoding="utf-8") as out:
            for row in rows:
                if time.time()>=deadline:
                    break
                board=chess.Board(row["fen"])
                record=dict(row)
                record["worker_cpu"]=cpu
                record["resolving_uci"]=[]
                record["analyses"]=[]
                reason="no_analysis"
                for iteration in range(2):
                    info=analyse(engine,board)
                    record["analyses"].append(info)
                    if info is None or info["total_nodes"]<NODES:
                        reason="incomplete_reference"; break
                    if info["mate"] is not None or info["white_cp"] is None or abs(info["white_cp"])>1000:
                        reason="mate_or_extreme"; break
                    if not info["pv"]:
                        reason="empty_pv"; break
                    best=chess.Move.from_uci(info["pv"][0])
                    if not forcing(board,best):
                        drift=abs(info["white_cp"]-info["prior_exact_cp"]) if info["prior_exact_cp"] is not None else 10**9
                        if drift>40 or info["nodes"]<10000:
                            reason="unstable_exact_iterations"; break
                        reason="accepted"
                        record["fen_quiet"]=board.fen()
                        record["sf19_white_cp"]=info["white_cp"]
                        record["score_drift_cp"]=drift
                        break
                    if iteration==1:
                        reason="still_forcing_after_resolution"; break
                    progressed=False
                    for uci in info["pv"]:
                        move=chess.Move.from_uci(uci)
                        if not forcing(board,move):
                            break
                        board.push(move)
                        record["resolving_uci"].append(uci)
                        progressed=True
                        if len(record["resolving_uci"])>=MAX_LEAF_PLY:
                            break
                    if not progressed or board.is_game_over(claim_draw=True) or len(record["resolving_uci"])>=MAX_LEAF_PLY:
                        reason="forcing_resolution_limit_or_terminal"; break
                record["status"]=reason
                counters[reason]+=1
                counters["processed"]+=1
                out.write(json.dumps(record,separators=(",",":"))+"\n")
                if counters["processed"]%25==0:
                    out.flush()
                if counters["processed"]%100==0:
                    print(json.dumps({"cpu":cpu,"processed":counters["processed"],"accepted":counters["accepted"],"elapsed_s":round(time.monotonic()-started,1)}),flush=True)
    finally:
        engine.quit()
    return {"cpu":cpu,"counts":dict(counters),"elapsed_s":time.monotonic()-started,"file":file.name,"sha256":sha(file),"planned_rows":len(rows)}


def label(seconds):
    plan=json.loads((HERE/"plan.json").read_text())
    assert sha(HERE/"selection.jsonl")==plan["selection_sha256"]
    rows=[json.loads(line) for line in (HERE/"selection.jsonl").read_text().splitlines()]
    deadline=time.time()+seconds
    results=[]
    with ProcessPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(worker,cpu,rows[index::4],deadline) for index,cpu in enumerate((5,6,7,8))]
        for future in as_completed(futures):
            result=future.result()
            results.append(result)
            print(json.dumps({"event":"worker_done",**result}),flush=True)
    (HERE/"label-run.json").write_text(json.dumps({"deadline_utc":datetime.fromtimestamp(deadline,timezone.utc).isoformat(),"workers":results},indent=2)+"\n",encoding="utf-8")


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("stage",choices=("prepare","label"))
    parser.add_argument("--seconds",type=int,default=840)
    args=parser.parse_args()
    HERE.mkdir(parents=True,exist_ok=True)
    prepare() if args.stage=="prepare" else label(args.seconds)

"""Training-only constrained fit of the original eleven positional features."""
from __future__ import annotations
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

os.environ["OPENBLAS_NUM_THREADS"]="1"
os.environ["OMP_NUM_THREADS"]="1"
import chess
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT))
from lab.odin.training.features_ref import FEATURE_NAMES,extract
sys.path.insert(0,str(ROOT/"odin"))
from board_nb import from_fen
from eval_nb import pesto

# Bounds are coefficient units in cp per raw feature, fixed before looking at
# the new reference labels. The model is a small correction to existing PeSTO.
MG_BOUNDS=[(-50,0),(-50,0),(0,50),(0,40),(-120,0),(-30,0),(0,40),(0,80),(0,60),(0,60),(-100,0)]
EG_BOUNDS=[(-50,0),(-50,0),(0,50),(0,40),(-120,0),(-40,0),(0,40),(0,80),(0,60),(0,20),(-20,0)]
CAP=400
RIDGES=(10.,100.,1000.)
HUBER=100.


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze_fit_plan():
    target=HERE/"fit-plan.json"
    if target.exists():
        return
    spec={"frozen_utc":datetime.now(timezone.utc).isoformat(),"feature_names":list(FEATURE_NAMES),
          "mg_bounds":dict(zip(FEATURE_NAMES,MG_BOUNDS)),"eg_bounds":dict(zip(FEATURE_NAMES,EG_BOUNDS)),
          "correction_clip_cp":CAP,"ridge_grid":RIDGES,"huber_cp":HUBER,"irls_iterations":6,
          "inner_training_partition":"sha256('quiet-inner-v1'+opening_key) mod5 equals0",
          "choice":"Lowest internal-training-holdout MAE, ties prefer larger ridge; final validation not consulted.",
          "standardization":"Training-subset RMS only; no intercept/centering so color symmetry is preserved.",
          "baseline":"Exact existing PeSTO with its actual10cp side-to-move tempo; white orientation.",
          "quantization":"Round MG/EG coefficients to nearest integer after fitting; report both metrics without validation retuning.",
          "deduplication":"Exclude every canonical quiet-position key shared across original train/validation; retain one deterministic row within each partition.",
          "confidence":"2000 deterministic opening-family bootstrap resamples of validation per-row MAE improvement; descriptive offline uncertainty only."}
    target.write_text(json.dumps(spec,indent=2)+"\n",encoding="utf-8")
    print("FIT PLAN FROZEN",flush=True)


def metrics(y,pred):
    diff=y-pred
    return {"mae_cp":float(np.mean(np.abs(diff))),"rmse_cp":float(np.sqrt(np.mean(diff*diff))),
            "median_abs_cp":float(np.median(np.abs(diff))),"p90_abs_cp":float(np.quantile(np.abs(diff),.9))}


def fitted(x,y,mask,ridge):
    # Box-constrained ridge/Huber IRLS. Coordinate descent solves each convex
    # weighted quadratic directly in standardized coefficient coordinates.
    scale=np.sqrt(np.mean(x[mask]**2,axis=0))
    scale[scale<1e-8]=1
    xs=x[mask]/scale
    target=y[mask]
    bounds=np.asarray(MG_BOUNDS+EG_BOUNDS,dtype=float)
    low,high=bounds[:,0]*scale,bounds[:,1]*scale
    coef=np.zeros(x.shape[1])
    weights=np.ones(len(target))
    for _ in range(6):
        gram=xs.T@(xs*weights[:,None])+np.eye(x.shape[1])*ridge
        rhs=xs.T@(weights*target)
        for sweep in range(250):
            biggest=0.
            for j in range(x.shape[1]):
                previous=coef[j]
                raw=(rhs[j]-gram[j]@coef+gram[j,j]*previous)/gram[j,j]
                coef[j]=np.clip(raw,low[j],high[j])
                biggest=max(biggest,abs(coef[j]-previous))
            if biggest<1e-7:
                break
        error=target-xs@coef
        weights=np.minimum(1.,HUBER/np.maximum(np.abs(error),1e-12))
    result=coef/scale
    assert np.all(result>=bounds[:,0]-1e-6) and np.all(result<=bounds[:,1]+1e-6)
    return result


def main():
    freeze_fit_plan()
    plan=json.loads((HERE/"fit-plan.json").read_text())
    assert plan["mg_bounds"]=={k:list(v) for k,v in zip(FEATURE_NAMES,MG_BOUNDS)}
    all_rows=[]
    status=Counter()
    for file in sorted(HERE.glob("labels-cpu*.jsonl")):
        for line in file.read_text().splitlines():
            row=json.loads(line)
            status[row["status"]]+=1
            if row["status"]=="accepted":
                all_rows.append(row)
    identities=defaultdict(list)
    for row in all_rows:
        board=chess.Board(row["fen_quiet"])
        assert board.is_valid() and not board.is_check()
        key=" ".join(board.fen(en_passant="legal").split()[:4])
        identities[key].append(row)
    cross=set(k for k,rows in identities.items() if len({r["split"] for r in rows})>1)
    records=[min(rows,key=lambda r:r["selection_key"]) for key,rows in identities.items() if key not in cross]
    records.sort(key=lambda r:r["selection_key"])
    features=[];labels=[];bases=[];phases=[];valid=[];inner=[]
    for row in records:
        board=chess.Board(row["fen_quiet"])
        # Verify every derived board is exactly the recorded legal PV prefix.
        replay=chess.Board(row["fen"])
        for uci in row["resolving_uci"]:
            replay.push_uci(uci)
        assert replay.fen()==board.fen()
        assert not board.is_capture(chess.Move.from_uci(row["analyses"][-1]["pv"][0]))
        features.append(extract(board))
        labels.append(row["sf19_white_cp"])
        raw=pesto(from_fen(board.fen()),tempo=True)
        bases.append(raw if board.turn else -raw)
        phase=sum(len(board.pieces(p,c))*w for c in chess.COLORS
                  for p,w in ((chess.KNIGHT,1),(chess.BISHOP,1),(chess.ROOK,2),(chess.QUEEN,4)))
        phases.append(min(24,phase)/24)
        valid.append(row["split"]=="validation")
        inner.append(int(hashlib.sha256(("quiet-inner-v1"+row["opening_key"]).encode()).hexdigest(),16)%5==0)
    raw_x=np.asarray(features,float)
    ratio=np.asarray(phases)[:,None]
    x=np.concatenate((raw_x*ratio,raw_x*(1-ratio)),axis=1)
    y=np.asarray(labels,float);base=np.asarray(bases,float)
    valid=np.asarray(valid,bool);train=~valid;inner=np.asarray(inner,bool)&train
    learn=train&~inner
    assert train.sum()>=500 and valid.sum()>=150 and inner.sum()>=100
    choices=[]
    for ridge in RIDGES:
        coef=fitted(x,y-base,learn,ridge)
        pred=base+np.clip(x@coef,-CAP,CAP)
        choices.append({"ridge":ridge,**metrics(y[inner],pred[inner])})
    chosen=min(choices,key=lambda r:(r["mae_cp"],-r["ridge"]))["ridge"]
    coef=fitted(x,y-base,train,chosen)
    quantized=np.rint(coef)
    correction=np.clip(x@coef,-CAP,CAP)
    prediction=base+correction
    quantized_prediction=base+np.rint(np.clip(x@quantized,-CAP,CAP))
    performance={}
    for label,mask in (("train",train),("validation",valid)):
        performance[label]={"baseline":metrics(y[mask],base[mask]),
                            "corrected":metrics(y[mask],prediction[mask]),
                            "integer_coefficients":metrics(y[mask],quantized_prediction[mask])}
    buckets={}
    for bucket in ("middlegame","attack","ending"):
        mask=valid&np.asarray([r["bucket"]==bucket for r in records])
        if mask.sum():
            buckets[bucket]={"rows":int(mask.sum()),"baseline":metrics(y[mask],base[mask]),
                             "integer_coefficients":metrics(y[mask],quantized_prediction[mask])}
    # Clustered interval uses the original untouched opening-family units.
    family=defaultdict(lambda:[0.,0])
    for i,row in enumerate(records):
        if valid[i]:
            improvement=abs(y[i]-base[i])-abs(y[i]-quantized_prediction[i])
            family[row["opening_key"]][0]+=improvement
            family[row["opening_key"]][1]+=1
    grouped=np.asarray(list(family.values()),float)
    rng=np.random.default_rng(2026090503)
    samples=[]
    for _ in range(2000):
        draw=grouped[rng.integers(0,len(grouped),len(grouped))].sum(axis=0)
        samples.append(draw[0]/draw[1])
    improvement=performance["validation"]["baseline"]["mae_cp"]-performance["validation"]["integer_coefficients"]["mae_cp"]
    output={"status":"COMPLETE","created_utc":datetime.now(timezone.utc).isoformat(),
            "selection_sha256":digest(HERE/"selection.jsonl"),"fit_plan_sha256":digest(HERE/"fit-plan.json"),
            "label_file_sha256":{p.name:digest(p) for p in HERE.glob("labels-cpu*.jsonl")},
            "screen_status":dict(status),"accepted_before_dedup":len(all_rows),"cross_partition_position_keys_excluded":len(cross),
            "deduplicated_rows":len(records),"train_rows":int(train.sum()),"validation_rows":int(valid.sum()),
            "inner_train_rows":int(learn.sum()),"inner_holdout_rows":int(inner.sum()),
            "validation_families":len(family),"reference":"Stockfish19,100k fixed-node exact streaming/stable quiet-leaf labels",
            "fit_choice":choices,"selected_ridge":chosen,"features":list(FEATURE_NAMES),
            "coefficients_mg":dict(zip(FEATURE_NAMES,coef[:11].tolist())),
            "coefficients_eg":dict(zip(FEATURE_NAMES,coef[11:].tolist())),
            "integer_mg":dict(zip(FEATURE_NAMES,quantized[:11].astype(int).tolist())),
            "integer_eg":dict(zip(FEATURE_NAMES,quantized[11:].astype(int).tolist())),
            "performance":performance,"validation_by_bucket":buckets,
            "validation_mae_improvement_cp":improvement,
            "validation_mae_improvement_percent":100*improvement/performance["validation"]["baseline"]["mae_cp"],
            "validation_family_bootstrap_95_cp":np.quantile(samples,[.025,.975]).tolist(),
            "correction_range_cp":[float(correction.min()),float(correction.max())],
            "fraction_corrections_clipped":float(np.mean(np.abs(x@coef)>CAP)),
            "resolved_forcing_rows":sum(bool(r["resolving_uci"]) for r in records),
            "source_hashes":{"features_ref.py":digest(ROOT/"lab/odin/training/features_ref.py"),"eval_nb.py":digest(ROOT/"odin/eval_nb.py")},
            "limitations":"Offline error reduction only. No native implementation/cost/game test or playing-strength claim. Feature model remains the same limited11 counts; labels are finite-budget and the training corpus shares established chess structures with broader play."}
    (HERE/"fit-result.json").write_text(json.dumps(output,indent=2)+"\n",encoding="utf-8")
    (HERE/"fit-records.jsonl").write_text("".join(json.dumps({"id":r["id"],"fen":r["fen_quiet"],"split":r["split"],"opening_key":r["opening_key"],"reference_cp":int(y[i]),"baseline_cp":int(base[i]),"predicted_cp":float(quantized_prediction[i])},separators=(",",":"))+"\n" for i,r in enumerate(records)),encoding="utf-8")
    print(json.dumps(output),flush=True)


if __name__=="__main__":
    if "--freeze-plan" in sys.argv:
        freeze_fit_plan()
    else:
        main()

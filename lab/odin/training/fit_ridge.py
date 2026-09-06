"""Fit and validate a colour-symmetric positional correction offline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import chess
import numpy as np

from lab.odin.training.features_ref import FEATURE_NAMES, extract


ROOT = Path(__file__).resolve().parents[3]
TRAINING = ROOT / "lab" / "odin" / "training"
ODIN = ROOT / "odin"
sys.path.insert(0, str(ODIN))
from board_nb import from_fen  # noqa: E402
from eval_nb import pesto  # noqa: E402


def pesto_white(board: chess.Board) -> int:
    value = pesto(from_fen(board.fen(en_passant="fen")), tempo=False)
    return value if board.turn == chess.WHITE else -value


def phase_ratio(board: chess.Board) -> float:
    phase = sum(len(board.pieces(piece, color)) * weight
                for color in (chess.WHITE, chess.BLACK)
                for piece, weight in ((chess.KNIGHT, 1), (chess.BISHOP, 1),
                                      (chess.ROOK, 2), (chess.QUEEN, 4)))
    return min(24, phase) / 24.0


def metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    residual = actual - predicted
    return {
        "mae_cp": round(float(np.mean(np.abs(residual))), 3),
        "rmse_cp": round(float(np.sqrt(np.mean(residual * residual))), 3),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", type=Path, default=TRAINING / "labels-sf19-n2000.jsonl")
    parser.add_argument("--ridge", type=float, default=20.0)
    parser.add_argument("--huber", type=float, default=200.0)
    parser.add_argument("--iterations", type=int, default=6)
    args = parser.parse_args()
    records = [json.loads(line) for line in args.labels.read_text(encoding="utf-8").splitlines()]
    if len(records) < 1_000:
        raise SystemExit("need at least 1,000 non-mate labels before fitting")
    features: list[tuple[int, ...]] = []
    labels: list[float] = []
    baseline: list[float] = []
    validation: list[bool] = []
    phase: list[float] = []
    for record in records:
        board = chess.Board(record["fen"])
        features.append(extract(board))
        labels.append(float(record["sf19_white_cp"]))
        baseline.append(float(pesto_white(board)))
        validation.append(record["split"] == "validation")
        phase.append(phase_ratio(board))
    raw_x = np.asarray(features, dtype=np.float64)
    y = np.asarray(labels, dtype=np.float64)
    base = np.asarray(baseline, dtype=np.float64)
    valid = np.asarray(validation, dtype=bool)
    train = ~valid
    if train.sum() < 500 or valid.sum() < 200:
        raise SystemExit("opening-family partitions are too small")
    # RMS-only scaling preserves zero as the symmetric no-advantage origin;
    # no intercept is fitted because a White-only bias would break mirroring.
    mg_phase = np.asarray(phase, dtype=np.float64)[:, None]
    # Every unit gets an independent MG and EG coefficient.  The two halves
    # share the same raw geometry and blend on the engine's 0..24 phase scale.
    x = np.concatenate((raw_x * mg_phase, raw_x * (1.0 - mg_phase)), axis=1)
    scale = np.sqrt(np.mean(x[train] * x[train], axis=0))
    scale[scale < 1e-9] = 1.0
    xs = x / scale
    residual = y - base
    fitted_scaled = np.zeros(x.shape[1], dtype=np.float64)
    weights = np.ones(int(train.sum()), dtype=np.float64)
    train_x = xs[train]
    train_target = residual[train]
    # Huber IRLS limits the influence of shallow-reference tactical swings;
    # mates are already excluded above.  It preserves the no-intercept,
    # colour-symmetric model and is entirely fitted on train opening families.
    for _ in range(args.iterations):
        gram = train_x.T @ (train_x * weights[:, None]) + np.eye(x.shape[1]) * args.ridge
        fitted_scaled = np.linalg.solve(gram, train_x.T @ (weights * train_target))
        error = train_target - train_x @ fitted_scaled
        weights = np.minimum(1.0, args.huber / np.maximum(np.abs(error), 1e-9))
    coefficient = fitted_scaled / scale
    correction = x @ coefficient
    prediction = base + correction
    report = {
        "labels": len(records), "train_labels": int(train.sum()), "validation_labels": int(valid.sum()),
        "feature_names": list(FEATURE_NAMES),
        "feature_units": "White-minus-black signed integer geometry counts; independent MG/EG coefficients blend by material phase, with no runtime lookup positions.",
        "optimizer": {"ridge": args.ridge, "huber_cp": args.huber, "irls_iterations": args.iterations},
        "coefficients_mg_cp_per_unit": {name: round(float(value), 6)
                                        for name, value in zip(FEATURE_NAMES, coefficient[:len(FEATURE_NAMES)])},
        "coefficients_eg_cp_per_unit": {name: round(float(value), 6)
                                        for name, value in zip(FEATURE_NAMES, coefficient[len(FEATURE_NAMES):])},
        "baseline": {"train": metrics(y[train], base[train]), "validation": metrics(y[valid], base[valid])},
        "corrected": {"train": metrics(y[train], prediction[train]), "validation": metrics(y[valid], prediction[valid])},
        "acceptance": "Candidate weights require lower validation error and separate native symmetry/cost/game gates before merger.",
    }
    (TRAINING / "ridge-fit-sf19-n2000.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("ODIN RIDGE FIT " + json.dumps(report), flush=True)


if __name__ == "__main__":
    main()

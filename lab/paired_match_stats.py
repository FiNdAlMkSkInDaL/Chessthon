"""Validate and analyse paired, colour-swapped engine match JSONL.

The unit of resampling is an opening pair, not an individual game.  This is
important because the two games which share a FEN are correlated.  Protocol,
clock and illegal-move failures are reported separately and their whole pair
is excluded from the strength estimate; a candidate failure always prevents a
release PASS.

Supported game rows are the legacy :mod:`lab.gauntlet` schema and the typed
``lab.container_match`` schema.  Metadata rows such as ``run_start`` and
``run_summary`` are ignored.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from harness.referee import FAILED_TERMINATIONS


DEFAULT_BOOTSTRAP_SAMPLES = 20_000
DEFAULT_BOOTSTRAP_SEED = 20260904
DEFAULT_CONFIDENCE = 0.95
DEFAULT_THRESHOLD = 0.50
DEFAULT_MIN_PAIRS = 20
BUCKET_NAMES = ("LL", "LD", "DD", "WD", "WW")
VALID_RESULTS = frozenset({"white", "black", "draw", "void"})


@dataclass(frozen=True)
class LocatedRow:
    payload: dict[str, Any]
    source: str
    line: int

    @property
    def where(self) -> str:
        return f"{self.source}:{self.line}"


@dataclass(frozen=True)
class NormalizedGame:
    row: LocatedRow
    fen: str
    candidate_colour: str
    result: str
    points: float | None
    termination: str
    candidate_failure: bool
    opponent_failure: bool
    white_identity: str | None
    black_identity: str | None
    opening_index: Any

    @property
    def candidate_identity(self) -> str | None:
        return self.white_identity if self.candidate_colour == "white" else self.black_identity

    @property
    def opponent_identity(self) -> str | None:
        return self.black_identity if self.candidate_colour == "white" else self.white_identity


def _is_game_row(row: dict[str, Any]) -> bool:
    row_type = row.get("type")
    if row_type is not None:
        return row_type == "game"
    return "fen" in row and "result" in row


def read_jsonl(paths: Sequence[Path]) -> tuple[list[LocatedRow], list[str]]:
    rows: list[LocatedRow] = []
    errors: list[str] = []
    for path in paths:
        resolved = path.expanduser().resolve()
        source = str(resolved)
        try:
            lines = resolved.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            errors.append(f"{source}: cannot read: {exc}")
            continue
        for line_no, text in enumerate(lines, 1):
            if not text.strip():
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                errors.append(f"{source}:{line_no}: invalid JSON: {exc.msg}")
                continue
            if not isinstance(payload, dict):
                errors.append(f"{source}:{line_no}: JSON row is not an object")
                continue
            if _is_game_row(payload):
                rows.append(LocatedRow(payload, source, line_no))
    return rows, errors


def _json_bool(value: Any, field: str, where: str, errors: list[str]) -> bool | None:
    if value is None:
        return None
    if type(value) is not bool:
        errors.append(f"{where}: {field} must be a JSON boolean")
        return None
    return value


def _candidate_colour(payload: dict[str, Any], where: str, errors: list[str]) -> str | None:
    colour = payload.get("candidate_colour", payload.get("candidate_color", payload.get("we")))
    if colour is not None:
        if colour not in {"white", "black"}:
            errors.append(f"{where}: candidate colour/we must be 'white' or 'black'")
            return None
        return colour

    white_role = payload.get("white_role")
    black_role = payload.get("black_role")
    if white_role == "candidate" and black_role != "candidate":
        return "white"
    if black_role == "candidate" and white_role != "candidate":
        return "black"
    errors.append(f"{where}: cannot determine exactly one candidate colour")
    return None


def _points(colour: str, result: str) -> float | None:
    if result == "draw":
        return 0.5
    if result == "void":
        return None
    return 1.0 if result == colour else 0.0


def _identity(payload: dict[str, Any], colour: str) -> str | None:
    # Content hashes are the strongest identity in container logs.  Legacy
    # gauntlets record the resolved player paths instead.
    for field in (f"{colour}_sha256", f"{colour}_image", colour):
        value = payload.get(field)
        if value is not None:
            return str(value)
    return None


def _infer_failures(colour: str, result: str, termination: str) -> tuple[bool, bool]:
    if termination not in FAILED_TERMINATIONS:
        return False, False
    if termination == "both_failed" or result == "void":
        return True, True
    if result not in {"white", "black"}:
        return False, False
    candidate_lost = result != colour
    return candidate_lost, not candidate_lost


def normalize_game(located: LocatedRow, errors: list[str]) -> NormalizedGame | None:
    payload = located.payload
    where = located.where
    fen = payload.get("fen")
    if not isinstance(fen, str) or not fen.strip():
        errors.append(f"{where}: fen must be a non-empty string")
        return None
    result = payload.get("result")
    if result not in VALID_RESULTS:
        errors.append(f"{where}: invalid result {result!r}")
        return None
    colour = _candidate_colour(payload, where, errors)
    if colour is None:
        return None
    termination = payload.get("termination", "")
    if not isinstance(termination, str):
        errors.append(f"{where}: termination must be a string")
        return None

    calculated_points = _points(colour, result)
    supplied_points = payload.get("candidate_points")
    if supplied_points is not None:
        if supplied_points not in {0, 0.0, 0.5, 1, 1.0}:
            errors.append(f"{where}: invalid candidate_points {supplied_points!r}")
        elif calculated_points is None or float(supplied_points) != calculated_points:
            errors.append(
                f"{where}: candidate_points {supplied_points!r} disagrees with "
                f"candidate colour/result ({calculated_points!r})"
            )

    explicit_candidate = None
    for field in ("candidate_failure", "our_fail"):
        if field in payload:
            explicit_candidate = _json_bool(payload[field], field, where, errors)
            break
    explicit_opponent = None
    for field in ("baseline_failure", "opponent_failure", "their_fail"):
        if field in payload:
            explicit_opponent = _json_bool(payload[field], field, where, errors)
            break

    inferred_candidate, inferred_opponent = _infer_failures(colour, result, termination)
    if explicit_candidate is not None and explicit_candidate != inferred_candidate:
        errors.append(
            f"{where}: candidate failure marker disagrees with {result}/{termination}"
        )
    # Legacy gauntlet logs deliberately record ``their_fail=false`` for a
    # both_failed void (there is no opponent win to attribute).  Accept that
    # established convention while still treating the pair as unusable.
    if (
        explicit_opponent is not None
        and explicit_opponent != inferred_opponent
        and termination != "both_failed"
    ):
        errors.append(
            f"{where}: opponent failure marker disagrees with {result}/{termination}"
        )

    return NormalizedGame(
        row=located,
        fen=fen,
        candidate_colour=colour,
        result=result,
        points=calculated_points,
        termination=termination,
        candidate_failure=(
            inferred_candidate if explicit_candidate is None else explicit_candidate
        ),
        opponent_failure=(
            inferred_opponent if explicit_opponent is None else explicit_opponent
        ),
        white_identity=_identity(payload, "white"),
        black_identity=_identity(payload, "black"),
        opening_index=payload.get("opening_index"),
    )


def _pair_groups(rows: Sequence[LocatedRow]) -> list[tuple[str, list[LocatedRow]]]:
    """Group explicit container pairs and consecutive legacy gauntlet pairs."""

    explicit: dict[tuple[str, str, str], list[LocatedRow]] = defaultdict(list)
    explicit_order: list[tuple[str, str, str]] = []
    legacy: dict[tuple[str, str], list[LocatedRow]] = defaultdict(list)
    legacy_order: list[tuple[str, str]] = []

    for located in rows:
        payload = located.payload
        run_id = str(payload.get("run_id", ""))
        if "pair" in payload:
            # A typed run_id is globally unique, so permit one run split over
            # multiple JSONL files.  Rows without one remain source-scoped.
            key = ("<run-id>" if run_id else located.source, run_id, str(payload["pair"]))
            if key not in explicit:
                explicit_order.append(key)
            explicit[key].append(located)
        else:
            key = (located.source, run_id)
            if key not in legacy:
                legacy_order.append(key)
            legacy[key].append(located)

    groups: list[tuple[str, list[LocatedRow]]] = []
    for scope, run_id, pair in explicit_order:
        pair_rows = explicit[(scope, run_id, pair)]
        sources = sorted({row.source for row in pair_rows})
        source_label = ",".join(sources)
        label = f"{source_label} run={run_id or '<none>'} pair={pair}"
        groups.append((label, pair_rows))
    for source, run_id in legacy_order:
        run_rows = legacy[(source, run_id)]
        for offset in range(0, len(run_rows), 2):
            pair_no = offset // 2 + 1
            label = f"{source} run={run_id or '<legacy>'} pair={pair_no}"
            groups.append((label, run_rows[offset : offset + 2]))
    return groups


def _validate_pair(
    label: str, located_rows: Sequence[LocatedRow], errors: list[str]
) -> list[NormalizedGame] | None:
    if len(located_rows) != 2:
        lines = ",".join(str(row.line) for row in located_rows) or "none"
        errors.append(
            f"{label}: expected exactly 2 games, found {len(located_rows)} "
            f"(lines {lines})"
        )
        # Still normalize a lone failure so the release gate reports it.
        for located in located_rows:
            normalize_game(located, errors)
        return None

    games: list[NormalizedGame] = []
    before = len(errors)
    for located in located_rows:
        game = normalize_game(located, errors)
        if game is not None:
            games.append(game)
    if len(games) != 2:
        return None

    first, second = games
    if first.fen != second.fen:
        errors.append(f"{label}: paired games use different FENs")
    if {first.candidate_colour, second.candidate_colour} != {"white", "black"}:
        errors.append(f"{label}: candidate colours were not swapped exactly once")
    if (
        first.opening_index is not None
        and second.opening_index is not None
        and first.opening_index != second.opening_index
    ):
        errors.append(f"{label}: opening_index differs across the pair")
    identities_present = all(
        value is not None
        for value in (
            first.white_identity,
            first.black_identity,
            second.white_identity,
            second.black_identity,
        )
    )
    if identities_present and (
        first.white_identity != second.black_identity
        or first.black_identity != second.white_identity
    ):
        errors.append(f"{label}: player identities were not swapped with colour")

    if len(errors) != before:
        return None
    return games


def percentile(values: Sequence[float], probability: float) -> float:
    if not values:
        raise ValueError("percentile requires at least one value")
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def paired_bootstrap_ci(
    pair_scores: Sequence[float],
    *,
    samples: int = DEFAULT_BOOTSTRAP_SAMPLES,
    seed: int = DEFAULT_BOOTSTRAP_SEED,
    confidence: float = DEFAULT_CONFIDENCE,
) -> tuple[float, float, float]:
    """Return percentile CI and bootstrap standard error for mean pair score."""

    if not pair_scores:
        raise ValueError("paired bootstrap requires at least one pair")
    if samples < 100:
        raise ValueError("bootstrap samples must be at least 100")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be between 0 and 1")
    rng = random.Random(seed)
    count = len(pair_scores)
    means = [
        sum(pair_scores[rng.randrange(count)] for _ in range(count)) / count
        for _ in range(samples)
    ]
    tail = (1.0 - confidence) / 2.0
    return percentile(means, tail), percentile(means, 1.0 - tail), statistics.pstdev(means)


def score_to_elo(score: float) -> float | str:
    if score <= 0.0:
        return "-inf"
    if score >= 1.0:
        return "+inf"
    return 400.0 * math.log10(score / (1.0 - score))


def _failure_counts(games: Iterable[NormalizedGame], attr: str) -> Counter[str]:
    return Counter(
        game.termination or "unspecified"
        for game in games
        if getattr(game, attr)
    )


def analyze_rows(
    payloads: Iterable[dict[str, Any] | LocatedRow],
    *,
    source: str = "<memory>",
    bootstrap_samples: int = DEFAULT_BOOTSTRAP_SAMPLES,
    seed: int = DEFAULT_BOOTSTRAP_SEED,
    confidence: float = DEFAULT_CONFIDENCE,
    threshold: float = DEFAULT_THRESHOLD,
    min_pairs: int = DEFAULT_MIN_PAIRS,
    initial_errors: Iterable[str] = (),
) -> dict[str, Any]:
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold must be between 0 and 1")
    if min_pairs < 1:
        raise ValueError("min_pairs must be at least 1")
    if bootstrap_samples < 100:
        raise ValueError("bootstrap samples must be at least 100")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be between 0 and 1")

    located: list[LocatedRow] = []
    for line, item in enumerate(payloads, 1):
        if isinstance(item, LocatedRow):
            if _is_game_row(item.payload):
                located.append(item)
        elif isinstance(item, dict):
            if _is_game_row(item):
                located.append(LocatedRow(item, source, line))
        else:
            raise TypeError("rows must be dictionaries or LocatedRow instances")

    errors = list(initial_errors)
    complete_pairs: list[list[NormalizedGame]] = []
    all_normalized: list[NormalizedGame] = []
    pair_groups = _pair_groups(located)
    for label, pair_rows in pair_groups:
        pair = _validate_pair(label, pair_rows, errors)
        # Normalize once more only for aggregate failure reporting when the
        # pair was structurally invalid.  Avoid duplicating diagnostics.
        if pair is None:
            scratch: list[str] = []
            for pair_row in pair_rows:
                game = normalize_game(pair_row, scratch)
                if game is not None:
                    all_normalized.append(game)
            continue
        complete_pairs.append(pair)
        all_normalized.extend(pair)

    candidate_failures = _failure_counts(all_normalized, "candidate_failure")
    opponent_failures = _failure_counts(all_normalized, "opponent_failure")
    included_pairs: list[list[NormalizedGame]] = []
    excluded_failure_pairs = 0
    for pair in complete_pairs:
        if any(
            game.candidate_failure or game.opponent_failure or game.points is None
            for game in pair
        ):
            excluded_failure_pairs += 1
        else:
            included_pairs.append(pair)

    included_games = [game for pair in included_pairs for game in pair]
    candidate_identities = {
        game.candidate_identity
        for game in included_games
        if game.candidate_identity is not None
    }
    opponent_identities = {
        game.opponent_identity
        for game in included_games
        if game.opponent_identity is not None
    }
    if len(candidate_identities) > 1:
        errors.append(
            "included pairs mix candidate identities: "
            + ", ".join(sorted(candidate_identities))
        )
    if len(opponent_identities) > 1:
        errors.append(
            "included pairs mix opponent identities: "
            + ", ".join(sorted(opponent_identities))
        )
    wins = sum(game.points == 1.0 for game in included_games)
    draws = sum(game.points == 0.5 for game in included_games)
    losses = sum(game.points == 0.0 for game in included_games)
    pair_scores = [sum(float(game.points) for game in pair) / 2.0 for pair in included_pairs]
    buckets = [0, 0, 0, 0, 0]
    for pair_score in pair_scores:
        buckets[int(round(pair_score * 4.0))] += 1

    score = sum(pair_scores) / len(pair_scores) if pair_scores else None
    lower = upper = bootstrap_se = None
    if pair_scores:
        lower, upper, bootstrap_se = paired_bootstrap_ci(
            pair_scores,
            samples=bootstrap_samples,
            seed=seed,
            confidence=confidence,
        )

    reasons: list[str] = []
    if errors:
        reasons.append(f"{len(errors)} validation error(s)")
    candidate_failure_total = sum(candidate_failures.values())
    if candidate_failure_total:
        reasons.append(f"{candidate_failure_total} candidate failure(s)")
    if len(included_pairs) < min_pairs:
        reasons.append(f"need {min_pairs} valid pairs, have {len(included_pairs)}")
    if lower is None:
        reasons.append("no paired confidence interval")
    elif lower <= threshold:
        reasons.append(
            f"lower confidence bound {lower:.4f} is not above threshold {threshold:.4f}"
        )
    verdict = "PASS" if not reasons else "FAIL"

    elo_estimate = score_to_elo(score) if score is not None else None
    elo_ci = (
        [score_to_elo(lower), score_to_elo(upper)]
        if lower is not None and upper is not None
        else None
    )
    return {
        "verdict": verdict,
        "reasons": reasons,
        "validation_errors": errors,
        "game_rows": len(located),
        "pair_groups": len(pair_groups),
        "complete_pairs": len(complete_pairs),
        "included_pairs": len(included_pairs),
        "excluded_failure_pairs": excluded_failure_pairs,
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "score": score,
        "pentanomial": dict(zip(BUCKET_NAMES, buckets, strict=True)),
        "bootstrap": {
            "method": "paired percentile bootstrap",
            "samples": bootstrap_samples,
            "seed": seed,
            "confidence": confidence,
            "standard_error": bootstrap_se,
            "score_ci": [lower, upper] if lower is not None else None,
        },
        "elo": {"estimate": elo_estimate, "ci": elo_ci},
        "candidate_failures": dict(candidate_failures),
        "opponent_failures": dict(opponent_failures),
        "identities": {
            "candidate": sorted(candidate_identities),
            "opponent": sorted(opponent_identities),
        },
        "gate": {"threshold": threshold, "min_pairs": min_pairs},
    }


def _percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2%}"


def _elo(value: float | str | None) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, str):
        return value
    return f"{value:+.1f}"


def print_human(stats: dict[str, Any]) -> None:
    print(
        f"pairs included={stats['included_pairs']}/{stats['pair_groups']} "
        f"complete={stats['complete_pairs']} failure-excluded={stats['excluded_failure_pairs']}"
    )
    print(
        f"candidate +{stats['wins']} ={stats['draws']} -{stats['losses']} "
        f"score={_percent(stats['score'])}"
    )
    buckets = stats["pentanomial"]
    print("pentanomial LL LD DD WD WW: " + " ".join(str(buckets[name]) for name in BUCKET_NAMES))
    interval = stats["bootstrap"]["score_ci"]
    if interval is None:
        print("paired bootstrap CI: n/a")
    else:
        print(
            f"paired bootstrap {stats['bootstrap']['confidence']:.1%} CI: "
            f"{_percent(interval[0])} .. {_percent(interval[1])} "
            f"(SE {_percent(stats['bootstrap']['standard_error'])}, "
            f"seed {stats['bootstrap']['seed']})"
        )
    elo_ci = stats["elo"]["ci"]
    if elo_ci is None:
        print("Elo estimate: n/a")
    else:
        print(
            f"Elo estimate {_elo(stats['elo']['estimate'])}, "
            f"CI {_elo(elo_ci[0])} .. {_elo(elo_ci[1])}"
        )
    print(
        f"candidate failures={stats['candidate_failures']} "
        f"opponent failures={stats['opponent_failures']}"
    )
    for error in stats["validation_errors"]:
        print(f"VALIDATION ERROR: {error}")
    detail = "; ".join(stats["reasons"]) if stats["reasons"] else (
        f"zero candidate failures and lower CI exceeds {stats['gate']['threshold']:.1%}"
    )
    print(f"{stats['verdict']}: {detail}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logs", nargs="+", type=Path, help="paired match JSONL log(s)")
    parser.add_argument("--bootstrap-samples", type=int, default=DEFAULT_BOOTSTRAP_SAMPLES)
    parser.add_argument("--seed", type=int, default=DEFAULT_BOOTSTRAP_SEED)
    parser.add_argument("--confidence", type=float, default=DEFAULT_CONFIDENCE)
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help="lower score-CI must be strictly above this (e.g. 0.48 for noninferiority)",
    )
    parser.add_argument(
        "--min-pairs",
        type=int,
        default=DEFAULT_MIN_PAIRS,
        help="minimum complete, failure-free opening pairs required for PASS",
    )
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    rows, load_errors = read_jsonl(args.logs)
    try:
        stats = analyze_rows(
            rows,
            bootstrap_samples=args.bootstrap_samples,
            seed=args.seed,
            confidence=args.confidence,
            threshold=args.threshold,
            min_pairs=args.min_pairs,
            initial_errors=load_errors,
        )
    except ValueError as exc:
        raise SystemExit(f"invalid analysis setting: {exc}") from exc
    if args.json:
        print(json.dumps(stats, indent=2, sort_keys=True, allow_nan=False))
    else:
        print_human(stats)
    raise SystemExit(0 if stats["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()

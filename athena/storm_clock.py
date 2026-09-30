"""Storm's position and search-evidence time manager (milliseconds).

The hard allowance always comes from the clock we already own. The increment
only informs the sustainable spending rate; it is credited after returning.
``SearchClock`` controls starting another iteration, never the native deadline.
Feed it completed, exact root iterations, including any aspiration re-search.

Gate: the native search must enforce an absolute deadline at every depth.
Keep this policy only after clock property tests and a full-game clock soak.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from statistics import median

HARD_MARGIN_MS = 320.0
MIN_SEARCH_MS = 50.0
INCREMENT_MS = 500.0
SOFT_RESERVE_MS = 1500.0
PLY_CAP = 600
MATE_THRESHOLD = 31_000


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def phase_units(bitboards) -> int:
    """Material phase from the engine's P,N,B,R,Q,K bitboards, both colours."""
    weights = (0, 1, 1, 2, 4, 0)
    return min(24, sum(int(bb).bit_count() * weights[i % 6]
                       for i, bb in enumerate(bitboards)))


def moves_to_go(game_ply: int, phase: int = 24) -> float:
    """Forecast our remaining decisions, without using FEN fullmove numbers.

    A receding fixed 40-move horizon hoards time throughout a normal game.
    Material phase and actual elapsed plies instead gradually shorten the
    forecast. Sparse positions still get at least eight decisions unless the
    referee's known ply cap is closer; low material is not proof of an easy win.
    """
    ply = max(0, int(game_ply))
    phase = _clamp(float(phase), 0.0, 24.0)
    forecast = max(8.0, 18.0 + 14.0 * phase / 24.0 - min(10.0, ply / 6.0))
    cap_moves = max(1, (PLY_CAP - ply + 1) // 2)
    return min(forecast, float(cap_moves))


def _clock_margins(time_left_ms: int) -> tuple[float, float]:
    """Scale reserves to the slice we actually hold.

    A large fixed hard margin plus 1500 ms soft reserve turns a 500 ms
    referee slice into a ~100 ms search. Contest 120 s still keeps a 320 ms
    panic buffer; 500 ms slices are unchanged (the 0.08*t cap is ~70 ms).
    """
    t = max(0.0, float(time_left_ms))
    hard_margin = max(40.0, min(HARD_MARGIN_MS, 0.08 * t + 30.0))
    soft_reserve = max(80.0, min(SOFT_RESERVE_MS, 0.22 * t))
    return hard_margin, soft_reserve


def allocation(
    time_left_ms: int,
    game_ply: int,
    phase: int = 24,
    root_moves: int = 30,
    in_check: bool = False,
) -> tuple[str, float, float]:
    """Return mode, initial soft target, absolute hard allowance from *now*.

    The caller must subtract setup time first. The search must start its hard
    deadline before allocating its own arrays, then enforce that deadline in
    native search. A single legal move needs no decision; its optional search
    is deliberately short. Few legal moves otherwise do not imply easy chess.
    """
    hard_margin, soft_reserve = _clock_margins(time_left_ms)
    available = max(0.0, float(time_left_ms) - hard_margin)
    if available < MIN_SEARCH_MS:
        return "panic", 0.0, 0.0

    horizon = moves_to_go(game_ply, phase)
    bank = max(0.0, float(time_left_ms) - soft_reserve)
    soft = bank / horizon + 0.85 * INCREMENT_MS
    ply = max(0, int(game_ply))
    if ply < 12 and root_moves > 1:
        # From the start position the Swiss is decided; buy one extra ply of ID.
        soft *= 1.12
    if in_check and root_moves > 1:
        soft *= 1.08
    if phase <= 6 and ply >= 80 and root_moves > 1:
        # Low material, long game: spend to convert before the 600-ply draw.
        soft *= 1.10
    soft = min(available, soft)
    hard = min(available, max(MIN_SEARCH_MS, 3.25 * soft))
    if root_moves == 1:
        soft = min(soft, 30.0)
        hard = min(hard, 100.0)
    return "search", float(soft), float(hard)


@dataclass(frozen=True, slots=True)
class Iteration:
    depth: int
    move: int
    score: int
    elapsed_ms: float
    nodes: int
    aspiration_failed: bool = False
    root_effort: float | None = None


class SearchClock:
    """Reallocate time according to evidence from this position's search.

    ``complete(...)`` is called once after each completed exact iteration.
    ``should_start(elapsed_ms)`` is queried before the next one. An aborted
    search or aspiration bound is never evidence of a stable best move.
    Root effort, when provided, is the fraction of the iteration's nodes spent
    on its eventual best root move; it is supporting evidence, not a score.
    """

    def __init__(self, soft_ms: float, hard_ms: float, root_moves: int = 30):
        self.hard_ms = max(0.0, float(hard_ms))
        self.soft_ms = _clamp(float(soft_ms), 0.0, self.hard_ms)
        self.root_moves = int(root_moves)
        self.iterations: list[Iteration] = []

    def complete(
        self,
        depth: int,
        move: int,
        score: int,
        iteration_ms: float,
        nodes: int,
        aspiration_failed: bool = False,
        root_effort: float | None = None,
    ) -> None:
        """Record one fully searched depth, including its aspiration retries."""
        if self.iterations and depth <= self.iterations[-1].depth:
            raise ValueError("Only one completed exact result per increasing depth")
        effort = None if root_effort is None else _clamp(root_effort, 0.0, 1.0)
        self.iterations.append(Iteration(
            int(depth), int(move), int(score), max(0.0, float(iteration_ms)),
            max(0, int(nodes)), bool(aspiration_failed), effort,
        ))
        # Five completed depths cover stability and odd/even cost swings.
        del self.iterations[:-5]

    @property
    def factor(self) -> float:
        """Current uncertainty multiplier; static advantage never discounts it."""
        records = self.iterations
        if len(records) < 2:
            return 1.0
        latest, previous = records[-1], records[-2]
        factor = 1.0
        recent_moves = records[-4:]
        changes = sum(a.move != b.move for a, b in zip(recent_moves, recent_moves[1:]))
        if latest.move != previous.move:
            factor += 0.55
        factor += 0.18 * max(0, changes - 1)
        drop = previous.score - latest.score
        factor += min(0.60, max(0, drop) / 160.0)
        factor += min(0.25, max(0, -drop) / 400.0)
        if latest.aspiration_failed:
            factor += 0.25
        if previous.aspiration_failed:
            factor += 0.10

        stable = 1
        for record in reversed(records[:-1]):
            if record.move != latest.move:
                break
            stable += 1
        recent = records[-3:]
        spread = max(r.score for r in recent) - min(r.score for r in recent)
        settled = (stable >= 3 and spread <= 32
                   and not any(r.aspiration_failed for r in records[-2:]))
        if settled:
            factor *= 0.80
            if stable >= 5:
                factor *= 0.82
            if latest.root_effort is not None and latest.root_effort >= 0.90:
                factor *= 0.90
            if abs(latest.score) >= 450:
                # Winning/losing shells: do not spend the bank proving a known PV.
                factor *= 0.78
        if latest.root_effort is not None and latest.root_effort < 0.45:
            factor *= 1.10
        return _clamp(factor, 0.55, 2.40)

    @property
    def target_ms(self) -> float:
        return min(self.hard_ms, self.soft_ms * self.factor)

    @property
    def predicted_next_ms(self) -> float:
        """Cost forecast from local measurements, with no assumed machine NPS.

        Geometric means of adjacent growth factors temper alternating cheap
        and expensive depths. Time and node growth together tolerate timer
        noise in tiny early passes and temporary CPU scheduling variation.
        This estimate controls launch decisions, never replaces the deadline.
        """
        records = self.iterations
        if not records:
            return 0.0
        growth = []
        for older, newer in zip(records, records[1:]):
            ratios = []
            if older.elapsed_ms >= 1.0 and newer.elapsed_ms >= 1.0:
                ratios.append(newer.elapsed_ms / older.elapsed_ms)
            if older.nodes > 0 and newer.nodes > 0:
                ratios.append(newer.nodes / older.nodes)
            if ratios:
                growth.append(_clamp(float(median(ratios)), 0.5, 12.0))
        if len(growth) >= 2:
            estimate = median(sqrt(a * b) for a, b in zip(growth, growth[1:]))
        elif growth:
            estimate = growth[0]
        else:
            estimate = 2.5
        return records[-1].elapsed_ms * _clamp(float(estimate), 1.3, 6.0)

    def should_start(self, elapsed_ms: float) -> bool:
        """Whether another complete depth is worth attempting within our clock."""
        elapsed = max(0.0, float(elapsed_ms))
        remaining = self.hard_ms - elapsed
        if remaining <= 2.0:
            return False
        if not self.iterations:
            return True
        latest = self.iterations[-1]
        if self.root_moves == 1 or latest.score >= MATE_THRESHOLD:
            return False
        # A tiny early pass says too little about either chess or the branching
        # factor to pre-empt useful search. The native deadline still applies.
        if latest.depth < 3:
            return True
        if elapsed >= self.target_ms:
            return False
        predicted = self.predicted_next_ms
        if predicted > remaining * 1.10:
            return False
        # Do not strand half the budget on an optimistic cost estimate. Once
        # most of the target has been used, avoid a large predictable overshoot.
        if elapsed >= 0.65 * self.target_ms:
            return elapsed + predicted <= 1.25 * self.target_ms
        return True

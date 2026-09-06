"""Frozen JSON match-plan binding, portable and free of engine imports.

Plan schema version 1:
  schema_version, base_ms, increment_ms, init_budget_s, ply_cap, packages,
  source_provenance, suites: {NAME: {candidate_sha256, baseline_sha256,
  openings_sha256, openings: [FEN...], min_pairs, threshold,
  criterion: 'paired_ci_lower' | 'raw_score',
  lanes: [{id, cpu, opening_indices: [index...]}]}}

Each suite's lane slices must cover every opening exactly once. Each opening
is played twice with colour reversal, and all game IDs are local to a lane.
threshold is strict: paired_ci_lower (default) compares the lower 95% paired
bootstrap score bound; raw_score compares the final complete-sample score.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path

TOOLS = (
    'lab/odin/release/linux_match.py', 'lab/odin/release/plan.py',
    'lab/odin/release/validate_match.py', 'lab/laptop_match.py',
    'lab/laptop_runner.py', 'lab/release_audit.py', 'lab/paired_match_stats.py',
)
HARNESS = ('referee.py', 'rules.py', 'runner.py', 'sandbox.py')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_provenance(root, harness_root):
    return {**{name: digest(Path(root)/name) for name in TOOLS},
            **{'official/harness/'+name: digest(Path(harness_root)/'harness'/name)
               for name in HARNESS}}


@dataclass(frozen=True)
class GamePlan:
    game: int
    pair: int
    opening_index: int
    fen: str
    white_role: str
    black_role: str
    white_cpu: int
    black_cpu: int


def validate_plan(plan):
    import chess
    if plan.get('schema_version') != 1:
        raise ValueError('Expected frozen plan schema_version 1')
    for key, expected in [('base_ms',120000),('increment_ms',500),
                          ('init_budget_s',90.0),('ply_cap',600)]:
        if plan.get(key) != expected:
            raise ValueError(f'Unexpected competition clock/rules: {key}')
    if not plan.get('source_provenance') or not plan.get('packages'):
        raise ValueError('Source/runtime provenance is required')
    if not plan.get('suites'):
        raise ValueError('At least one named suite is required')
    for name, suite in plan['suites'].items():
        for key in ('candidate_sha256','baseline_sha256','openings_sha256'):
            value = suite.get(key, '')
            if len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
                raise ValueError(f'{name}: invalid {key}')
        openings = suite['openings']
        if not openings or len(set(openings)) != len(openings):
            raise ValueError(f'{name}: duplicate/empty opening FENs')
        for fen in openings:
            board = chess.Board(fen)
            if not board.is_valid() or board.outcome(claim_draw=True) or board.ply()>=600:
                raise ValueError(f'{name}: invalid or terminal opening')
        lanes = suite['lanes']
        if len({lane['id'] for lane in lanes}) != len(lanes):
            raise ValueError(f'{name}: duplicate lane ID')
        indices = [index for lane in lanes for index in lane['opening_indices']]
        if sorted(indices) != list(range(len(openings))):
            raise ValueError(f'{name}: lane coverage must include every opening exactly once')
        if any(type(lane['cpu']) is not int or lane['cpu']<0 or not lane['opening_indices'] for lane in lanes):
            raise ValueError(f'{name}: invalid CPU or empty lane')
        if len({lane['cpu'] for lane in lanes}) != len(lanes):
            raise ValueError(f'{name}: concurrent suite lanes require distinct CPUs')
        if type(suite['min_pairs']) is not int or suite['min_pairs']<1 or suite['min_pairs']>len(openings):
            raise ValueError(f'{name}: invalid minimum pair count')
        if not 0 <= suite['threshold'] <= 1:
            raise ValueError(f'{name}: invalid threshold')
        if suite.get('criterion','paired_ci_lower') not in ('paired_ci_lower','raw_score'):
            raise ValueError(f'{name}: unknown statistical criterion')


def lane_plans(suite, lane_id):
    lanes = [lane for lane in suite['lanes'] if lane['id']==lane_id]
    if len(lanes) != 1:
        raise ValueError('Unknown/nonunique lane ID')
    lane = lanes[0]
    result = []
    for pair_number, index in enumerate(lane['opening_indices'], 1):
        for first_role, second_role in [('candidate','baseline'),('baseline','candidate')]:
            result.append(GamePlan(len(result)+1, pair_number, index,
                                   suite['openings'][index], first_role, second_role,
                                   lane['cpu'], lane['cpu']))
    return result


def bind_lane(plan, suite_name, lane_id, cpu, openings, openings_hash,
              candidate_hash, baseline_hash, base_ms, increment_ms):
    validate_plan(plan)
    suite = plan['suites'][suite_name]
    expected = (suite['candidate_sha256'],suite['baseline_sha256'],suite['openings_sha256'],
                tuple(suite['openings']),plan['base_ms'],plan['increment_ms'])
    actual = (candidate_hash,baseline_hash,openings_hash,tuple(openings),base_ms,increment_ms)
    if actual != expected:
        raise ValueError('Archive, opening file or clock differs from the frozen plan')
    plans = lane_plans(suite, lane_id)
    if plans[0].white_cpu != cpu:
        raise ValueError('CPU differs from frozen lane')
    return plans

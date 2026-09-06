"""Isolated bitops equivalence and optional microbenchmark; no engine import.

Run tests: python -m unittest lab.storm.test_bitops -v
Run benchmark: python -m lab.storm.test_bitops --bench
"""

import json
import platform
import random
from statistics import median
import sys
import time
import unittest

import numpy as np
from numba import njit

from storm.bitops_nb import lsb, popc


# V3/initial Storm function bodies, kept here to avoid compiling the engine.
@njit(cache=False)
def original_lsb(bb):
    v = np.uint64(bb)
    c = np.int32(0)
    if (v & np.uint64(0xFFFFFFFF)) == 0:
        v >>= np.uint64(32)
        c += 32
    if (v & np.uint64(0xFFFF)) == 0:
        v >>= np.uint64(16)
        c += 16
    if (v & np.uint64(0xFF)) == 0:
        v >>= np.uint64(8)
        c += 8
    if (v & np.uint64(0xF)) == 0:
        v >>= np.uint64(4)
        c += 4
    if (v & np.uint64(3)) == 0:
        v >>= np.uint64(2)
        c += 2
    if (v & np.uint64(1)) == 0:
        c += 1
    return c


@njit(cache=False)
def original_popc(bb):
    v = np.uint64(bb)
    n = 0
    while v:
        v &= v - np.uint64(1)
        n += 1
    return n


def sample_boards(count=12_000):
    rng = random.Random(241904)
    samples = [0, (1 << 64) - 1, 0x5555555555555555, 0xAAAAAAAAAAAAAAAA]
    for _ in range(count):
        value = rng.getrandbits(64)
        # Chess piece bitboards usually contain few bits; include those too.
        if len(samples) % 3 == 0:
            value &= rng.getrandbits(64) & rng.getrandbits(64)
        samples.append(value)
    return np.asarray(samples, dtype=np.uint64)


def sweep(operation):
    @njit(cache=False)
    def kernel(values, repeats):
        checksum = 0
        for _ in range(repeats):
            for value in values:
                checksum += operation(value)
        return checksum
    return kernel


def traverse(operation):
    @njit(cache=False)
    def kernel(values, repeats):
        checksum = 0
        for _ in range(repeats):
            for value in values:
                while value:
                    checksum += operation(value)
                    value &= value - np.uint64(1)
        return checksum
    return kernel


class BitopsTests(unittest.TestCase):
    def assert_exact(self, value):
        n = int(value)
        expected_lsb = (n & -n).bit_length() - 1 if n else 63
        expected_popc = n.bit_count()
        self.assertEqual(lsb(np.uint64(n)), expected_lsb)
        self.assertEqual(popc(np.uint64(n)), expected_popc)
        self.assertEqual(original_lsb(np.uint64(n)), expected_lsb)
        self.assertEqual(original_popc(np.uint64(n)), expected_popc)

    def test_explicit_zero_and_all_64_singletons(self):
        self.assert_exact(0)
        for bit in range(64):
            self.assert_exact(1 << bit)

    def test_every_pair_of_set_bits(self):
        for first in range(64):
            for second in range(first + 1, 64):
                self.assert_exact((1 << first) | (1 << second))

    def test_random_dense_sparse_and_patterned_boards(self):
        for value in sample_boards():
            self.assert_exact(value)

    def test_signed_input_cast_matches_original(self):
        for value in (-1, -(1 << 63), -256, 0, 1, (1 << 63) - 1):
            self.assertEqual(lsb(np.int64(value)), original_lsb(np.int64(value)))
            self.assertEqual(popc(np.int64(value)), original_popc(np.int64(value)))

    def test_entire_bit_traversal_matches_original(self):
        values = sample_boards(500)
        self.assertEqual(traverse(lsb)(values, 1), traverse(original_lsb)(values, 1))

    def test_codegen_emits_compiler_intrinsics(self):
        lsb(np.uint64(0))
        popc(np.uint64(0))
        self.assertIn("llvm.cttz.i64", lsb.inspect_llvm(lsb.signatures[0]))
        self.assertIn("llvm.ctpop.i64", popc.inspect_llvm(popc.signatures[0]))


def benchmark():
    # A short interleaved, warmed benchmark. Ratios are laptop evidence only;
    # engine nps must be measured separately on the runtime host.
    values = sample_boards(16_384)
    cases = [
        ("lsb_sweep", sweep(original_lsb), sweep(lsb), 48),
        ("lsb_traversal", traverse(original_lsb), traverse(lsb), 12),
        ("popcount_sweep", sweep(original_popc), sweep(popc), 48),
    ]
    report = {"platform": platform.platform(), "python": platform.python_version(),
              "note": "isolated warmed microbenchmark; not engine nps or Elo", "cases": {}}
    for name, baseline, candidate, repeats in cases:
        expected = baseline(values, repeats)
        assert candidate(values, repeats) == expected
        times = {"baseline": [], "intrinsic": []}
        for trial in range(7):
            order = [("baseline", baseline), ("intrinsic", candidate)]
            if trial % 2:
                order.reverse()
            for label, kernel in order:
                started = time.perf_counter()
                assert kernel(values, repeats) == expected
                times[label].append((time.perf_counter() - started) * 1000)
        old, new = median(times["baseline"]), median(times["intrinsic"])
        report["cases"][name] = {"baseline_ms": round(old, 4),
                                "intrinsic_ms": round(new, 4),
                                "speedup": round(old / new, 3),
                                "checksum": expected}
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    if "--bench" in sys.argv:
        benchmark()
    else:
        unittest.main()

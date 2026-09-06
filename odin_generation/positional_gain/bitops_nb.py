"""Exact bitboard primitives lowered by the bundled LLVM compiler.

No machine code, CPU feature assumptions or external library is shipped.
LLVM chooses instructions for the actual runtime host. Source references:
https://numba.readthedocs.io/en/stable/extending/high-level.html#implementing-intrinsics
https://llvmlite.readthedocs.io/en/stable/user-guide/ir/ir-builder.html
https://llvm.org/docs/LangRef.html#llvm-cttz-intrinsic

The old binary-split lsb returns 63 on zero; preserve that unusual behaviour.
Gate: exhaustive singleton/two-bit and random equivalence, then engine perft
and an equal-position throughput measurement on the Linux signer.
"""

import numpy as np
from llvmlite import ir
from numba import njit, types
from numba.extending import intrinsic


@intrinsic
def _lsb_u64(typing_context, value_type):
    if value_type != types.uint64:
        return None

    def codegen(context, builder, signature, args):
        # Setting the top bit cannot change any existing least-significant
        # bit. It also makes zero produce 63 with no undefined cttz operand.
        nonzero = builder.or_(args[0], ir.Constant(ir.IntType(64), 1 << 63))
        return builder.cttz(nonzero, ir.Constant(ir.IntType(1), 1))

    return types.int64(types.uint64), codegen


@intrinsic
def _popc_u64(typing_context, value_type):
    if value_type != types.uint64:
        return None

    def codegen(context, builder, signature, args):
        return builder.ctpop(args[0])

    return types.int64(types.uint64), codegen


@njit(cache=False, inline="always")
def lsb(bb):
    return _lsb_u64(np.uint64(bb))


@njit(cache=False, inline="always")
def popc(bb):
    return _popc_u64(np.uint64(bb))

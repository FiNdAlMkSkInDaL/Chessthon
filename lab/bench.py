"""nps / depth / time-to-move on the Linux signer. Laptop numbers are lies."""

from __future__ import annotations

import time

import chess

from board_nb import from_fen
from movegen_nb import generate_legal, perft
from search_nb import iterative_deepening
from time_nb import allocation

KIWIPETE = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"


def _banner() -> None:
    try:
        import core_nb

        print(
            f"numba ready={core_nb.NUMBA_READY} warmup={core_nb.WARMUP_S:.2f}s",
            flush=True,
        )
    except Exception as exc:
        print(f"numba unavailable: {exc}", flush=True)


def bench_perft(fen: str, depth: int) -> None:
    pos = from_fen(fen)
    t0 = time.perf_counter()
    nodes = perft(pos, depth)
    elapsed = time.perf_counter() - t0
    nps = nodes / elapsed if elapsed > 0 else 0
    print(f"perft {depth} nodes={nodes} {elapsed:.3f}s {nps:,.0f} nps", flush=True)


def bench_search(fen: str, time_ms: int, *, use_clock: bool = True) -> None:
    pos = from_fen(fen)
    packed = generate_legal(pos)
    if use_clock:
        _, soft, hard = allocation(time_ms, 20)
    else:
        soft = hard = float(time_ms)
    t0 = time.perf_counter()
    best = iterative_deepening(
        pos,
        packed,
        hard_ms=hard,
        soft_ms=soft,
        adjudicate=False,
        game_zkeys=[],
    )
    elapsed = time.perf_counter() - t0
    nodes = 0
    try:
        import core_nb

        nodes = core_nb.last_nodes()
    except Exception:
        from search_nb import _nodes as py_nodes

        nodes = py_nodes
    nps = nodes / elapsed if elapsed > 0 else 0
    from board_nb import move_uci

    print(
        f"search {time_ms}ms clock={use_clock} best={move_uci(best)} nodes={nodes} "
        f"{elapsed:.3f}s {nps:,.0f} nps",
        flush=True,
    )


def main() -> None:
    try:
        import core_nb

        if core_nb.HAS_NUMBA and not core_nb.NUMBA_READY:
            ok = core_nb.warmup()
            print(f"warmup ok={ok} {core_nb.WARMUP_S:.2f}s", flush=True)
    except Exception as exc:
        print(f"warmup skipped: {exc}", flush=True)
    _banner()
    print("startpos", flush=True)
    bench_perft(chess.STARTING_FEN, 5)
    print("kiwipete", flush=True)
    bench_perft(KIWIPETE, 4)
    bench_search(KIWIPETE, 3000)
    bench_search(KIWIPETE, 3000, use_clock=False)
    bench_search(KIWIPETE, 10_000)


if __name__ == "__main__":
    main()

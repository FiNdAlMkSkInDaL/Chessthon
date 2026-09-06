"""Cold import through the untouched official runner, plus legal clock probes."""
from pathlib import Path
import sys
import time
import chess
from harness.sandbox import local


def main():
    source=Path(sys.argv[1]).resolve()
    bot=local(source)
    began=time.perf_counter()
    try:
        bot.start(90.0)
        cold=time.perf_counter()-began
        print(f"COLD READY {cold:.3f}s",flush=True)
        assert cold<55.0, ('missed conservative init target',cold)
        for fen in (chess.STARTING_FEN,
                    'r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1',
                    '4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1',
                    '4k3/P7/8/8/8/8/7p/4K3 w - - 0 1'):
            began=time.perf_counter()
            uci=bot.move(fen,1000)
            elapsed=time.perf_counter()-began
            assert chess.Move.from_uci(uci) in chess.Board(fen).legal_moves
            assert elapsed<1.0,(uci,elapsed)
            print('PROTOCOL LEGAL',uci,round(elapsed,3),flush=True)
    finally:
        bot.stop()
    assert 'S4 ' in bot.stderr_tail, 'missing native search telemetry'
    print(bot.stderr_tail,flush=True)
    print('COLD PROTOCOL PASS',flush=True)


if __name__=='__main__': main()

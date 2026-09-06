"""Native/fallback value parity for fitted accumulator material and bishop pairs."""
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]


def main():
    sys.path.insert(0,str(ROOT/'odin_material'))
    import core_nb as core
    from board_nb import from_fen
    from eval_nb import evaluate
    import chess
    rows=[json.loads(s) for s in (HERE/'fit-records.jsonl').read_text().splitlines()]
    n=0
    for row in rows:
        b=chess.Board(row['fen'])
        for board in (b,b.mirror()):
            pos=from_fen(board.fen())
            bb,mb,st=core.pack_pos(pos)
            assert int(core.evaluate_nb(bb,st,0))==evaluate(pos),board.fen()
            n+=1
    report={'verdict':'PASS','native_fallback_cases':n,'scope':'Exact final integer material/pair evaluation, both colors.'}
    (HERE/'material-eval-parity.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__=='__main__':main()

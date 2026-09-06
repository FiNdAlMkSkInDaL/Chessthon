"""Bounded source transform from frozen history-perf r2; never edits r2."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
path = ROOT / "odin_history_compact/core_nb.py"
source = path.read_text(encoding="utf-8")
tree = ast.parse(source)
names = {n.name: [a.arg for a in n.args.args] for n in tree.body
         if isinstance(n, ast.FunctionDef) and n.name in ("qsearch_nb", "negamax_nb")}
drop = set()
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name in names:
        drop.add(next(a.lineno for a in node.args.args if a.arg == "null_tree"))
    elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in names:
        drop.add(node.args[names[node.func.id].index("null_tree")].lineno)
assert len(drop) == 13, len(drop)
source = "".join(line for number, line in enumerate(source.splitlines(keepends=True), 1) if number not in drop)
source = source.replace("if np.int32(st[FIFTY]) == 0 or null_tree:", "if np.int32(st[FIFTY]) == 0:")
source = source.replace("HIST_SEED if null_tree else history_append(hist_sig, st[KEY])", "history_append(hist_sig, st[KEY])")
source = source.replace("if not adjudicate and not null_tree:", "if not adjudicate:")
old = "    hlen2 = hlen\n    if not null_tree:\n        hist[hlen] = st[KEY]\n        hlen2 += 1\n"
assert source.count(old) == 2
source = source.replace(old, "    hist[hlen] = st[KEY]\n    hlen2 = hlen + 1\n")
source = source.replace("HIST_SEED = np.uint64(0xCBF29CE484222325)\n",
                        "HIST_SEED = np.uint64(0xCBF29CE484222325)\n"
                        "# A null pass starts a fresh virtual repetition ledger. Its scores remain\n"
                        "# context-separated until a legal zeroing move erases all prior positions.\n"
                        "NULL_HIST_SEED = np.uint64(0x84222325CBF29CE4)\n")
start = source.index("            score = -negamax_nb(", source.index("            make_null("))
end = source.index("            unmake_null(", start)
block = source[start:end]
old = "                hist,\n                hlen,\n                adjudicate,\n                cap_left,\n                has_pair,\n                hist_sig,\n"
new = "                hist[hlen:],\n                0,\n                adjudicate,\n                cap_left,\n                False,\n                NULL_HIST_SEED,\n"
assert block.count(old) == 1
block = block.replace(old, new)
source = source[:start] + (
    "            # The pass itself is not a legal game-history edge. Start a\n"
    "            # virtual game in unused storage, keeping its count-context\n"
    "            # distinct from the real game. A later zeroing legal move\n"
    "            # makes either prehistory unreachable and resets normally.\n"
) + block + source[end:]
assert "null_tree" not in source
ast.parse(source)
path.write_text(source, encoding="utf-8")
print("Compact source transform PASS; two recursive signatures restored, one null barrier")

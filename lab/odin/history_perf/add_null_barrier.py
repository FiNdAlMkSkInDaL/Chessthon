"""One-time bounded migration of recursive native null-history arguments."""
import ast
from pathlib import Path
import re

path = Path(__file__).resolve().parents[3] / "odin_history_perf/core_nb.py"
source = path.read_text(encoding="utf-8")
tree = ast.parse(source)
edits = []
lines = source.splitlines(keepends=True)
offsets = [0]
for line in lines:
    offsets.append(offsets[-1] + len(line))
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name in ("qsearch_nb", "negamax_nb"):
        assert "null_tree" not in [a.arg for a in node.args.args]
        arg = next(a for a in node.args.args if a.arg == "hist_sig")
        edits.append((offsets[arg.lineno], "    null_tree,\n"))
for offset, content in sorted(edits, reverse=True):
    source = source[:offset] + content + source[offset:]
pattern = r"(?m)^( {8,})(hist_sig|child_hist_sig|root_hist_sig),\n\1max_nodes,"
def insert(match):
    indent, name = match.groups()
    # Python search_root's args belong to root_search_nb, whose signature is
    # unchanged. Its three tuple constructions are excluded from the migration.
    if match.start() > source.index("\ndef search_root("):
        return match.group(0)
    value = "False" if name == "root_hist_sig" else "null_tree"
    return f"{indent}{name},\n{indent}{value},\n{indent}max_nodes,"
source, count = re.subn(pattern, insert, source)
assert count == 14, count
null_start = source.index("            score = -negamax_nb(", source.index("            make_null("))
null_end = source.index("            unmake_null(", null_start)
null_block = source[null_start:null_end]
assert null_block.count("                null_tree,\n") == 1
null_block = null_block.replace("                null_tree,\n", "                True,\n")
source = source[:null_start] + null_block + source[null_end:]
path.write_text(source, encoding="utf-8")
print(f"Inserted null_tree into two signatures and {count} recursive call sites")

"""Adapt the frozen r2 gates to the compact virtual-history policy."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "history_perf"
source = (BASE / "test_history_perf.py").read_text(encoding="utf-8")
source = source.replace('SOURCE = ROOT / "odin_history_perf"', 'SOURCE = ROOT / "odin_history_compact"')
source = source.replace('HIST_SEED=np.uint64(0xCBF29CE484222325),',
                        'HIST_SEED=np.uint64(0xCBF29CE484222325), NULL_HIST_SEED=np.uint64(0x84222325CBF29CE4),')
source = source.replace(', null_tree=False', '')
start = source.index('        # Synthetic null descendants retain no repetition ledger')
end = source.index('    def test_legal_null_triangulation_is_not_a_real_claim', start)
source = source[:start] + source[end:]
source = source.replace('the actual qsearch/negamax source-body null test above removes it.',
                        'the compact actual-null-call gate below removes it.')
(HERE / "test_history_compact.py").write_text(source, encoding="utf-8")

source = (BASE / "native_gate.py").read_text(encoding="utf-8")
source = source.replace('null_tree=False, ', '')
source = source.replace('    values["null_tree"] = True\n',
    '    real_prior_length = values["hlen"]\n'
    '    parent_history = values["hist"]\n'
    '    values.update(hist=parent_history[real_prior_length:], hlen=0,\n'
    '                  has_pair=False, hist_sig=c.NULL_HIST_SEED)\n')
source = source.replace('                 has_pair=False, hist_sig=c.HIST_SEED)',
                        '                 has_pair=False, hist_sig=c.NULL_HIST_SEED)')
source = source.replace('    before_history = values["hist"].copy()',
                        '    before_history = parent_history[:real_prior_length].copy()')
source = source.replace('    np.testing.assert_array_equal(values["hist"], before_history)\n'
                        '    assert not np.any(c.TT_KEY[:c.TT_SIZE]), "Null subtree stored a contextual score"',
                        '    np.testing.assert_array_equal(parent_history[:real_prior_length], before_history)\n'
                        '    virtual_context = c.score_tt_key(values["st"][c.KEY], int(values["st"][c.FIFTY]), values["cap_left"], np.uint64(c.history_append(c.NULL_HIST_SEED, values["st"][c.KEY])))\n'
                        '    real_context = c.score_tt_key(values["st"][c.KEY], int(values["st"][c.FIFTY]), values["cap_left"], np.uint64(c.history_append(c.HIST_SEED, values["st"][c.KEY])))\n'
                        '    assert virtual_context != real_context\n'
                        '    assert not c.tt_probe(np.uint64(real_context), 0, c.TT_KEY, c.TT_MOVE, c.TT_SCORE, c.TT_DEPTH, c.TT_GEN)[0]')
source = source.replace('Null search preserves existing real-edge cap/fifty policy but isolates repetition and contextual score TT throughout the synthetic subtree.',
                        'Each null begins a fresh virtual ledger in a distinct score-context namespace; legal zeroing erases either prior history and resumes the ordinary namespace. Post-barrier virtual repetitions are searched.')
(HERE / "native_gate.py").write_text(source, encoding="utf-8")

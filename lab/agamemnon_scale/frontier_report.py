"""Write the completed frontier cycle report from preserved experiment records."""
import json
from pathlib import Path
import numpy as np
from train import HERE,ROOT,sha
from frontier_summary import summarize
def main():
    result=summarize();assert len(result)==12, len(result)
    assert not any(r.get('nominate') for r in result.values()),'A nominee needs matches before this completed-no-promotion report'
    dest=HERE/'frontier';rank=[];fits=[]
    for p in sorted(dest.glob('rank-*/result.json')):
        r=json.loads(p.read_text());e=r['selected_epoch'];rank.append((p.parent.name,r['strength'],r['curve'][e-1]['regret']['mean'],e))
    for p in sorted(dest.glob('*/results.jsonl')):
        for r in map(json.loads,p.read_text().splitlines()):
            if r['type']!='complete':fits.append((p.parent.name,r['type'],r['metrics']['all']['model']['mae']))
    lines=['# Agamemnon frontier sandbox — completed 6 September 2026','',
    'No candidate earned promotion. Tempest r1 remains the Desktop release. This cycle implemented and tested new architecture, objective, data and search-integration branches; it did not run new matches or claim a strength gain.','',
    '## What the evidence says','',
    'The lowest static-error checkpoint is not the strongest demonstrated player. The original turn-aware neural replacement was faster than Tempest on these decision probes but made worse choices. A partial neural correction improved fixed-node decisions, while equal-wall gains were smaller and inconclusive. Neither direct child-move ranking nor this first small batch of search-leaf adaptation resolved that gap.','',
    'The most credible next push is to train the score that our search actually needs, on substantially broader root families, and validate decisions after search. New features remain an experiment, not an established missing ingredient. There is no evidence here that opponents possess one secret architecture.','',
    '## Branches actually implemented','',
    '1. **King-relative context:** add 2,700 original relative piece/own-king features to the pretrained 768-feature model. Zero initialization preserves its starting function. Two seeds, matched 512k positions, four continuation epochs and 45 adaptation epochs. Exact integer delta updates for unchanged king views; refresh only the view whose king changed. One native blend was tested. This small continuation did not establish a gain; it does not exhaust training this representation at larger scale.',
    '2. **Decision preference objective:** original differentiable pair loss on 8,241 preferred/inferior child pairs from training roots, with old search-state replay. Three strengths plus a zero-preference replay control, 12 epochs. Finite-difference gradient checks passed. Static child-choice regret fell from 325.97cp to 303.58cp for the selected fit, but its searched move choices failed the nomination screen. Direct child labels include tactical consequences, which may mismatch a static leaf target.',
    '3. **Hybrid evaluation:** quarter and half learned correction, preserving the corresponding fraction of Tempest\'s positional correction. No double-counted PeSTO. This isolates replacement damage without hiding neural inference cost.',
    '4. **Robust integration:** cap half-blend disagreement correction at 100cp, and independently retain Tempest\'s static pruning evaluation while using the hybrid at leaves. Both were tested separately; neither passed the original nomination rule.',
    '5. **Actual search-state replay:** instrument original qsearch stand-pat calls, systematic 257-call ring sampling, 80 roots split before labels (64 training, 16 development). Collected 2,496 valid nonterminal noncheck states; labelled with an offline 16k-node teacher, latest complete unbounded streaming iteration. Two continuation fits with different mined/replay balance; full, half and quarter influence tested.','',
    '## Controlled architecture errors','',
    '| Run | Stage | Development MAE (cp) |','|---|---|---:|']
    for name,stage,mae in fits:lines.append(f'| {name} | {stage} | {mae:.2f} |')
    lines+=['','## Move preference fit','', '| Run | Preference weight | Selected static child regret (cp) | Epoch |','|---|---:|---:|---:|']
    for name,w,error,epoch in rank:lines.append(f'| {name} | {w} | {error:.2f} | {epoch} |')
    lines+=['','The zero-preference control matches the update schedule/rate but uses a different shuffle seed; it is not a seed-matched causal estimate. All preference checkpoint selections reuse the existing development roots.','',
    '## Search-state adaptation','',
    'After excluding mate labels and values beyond 2,500cp, the fit used 1,967 sampled training states and 419 sampled development states, plus old search-state replay. Exact/mirror keys are deduplicated, and opposite-split sampled development keys are removed from replay. Public records have no original game IDs, so root splitting cannot establish game-family independence.','',
    '| Mined/replay balance | Sampled development MAE before → after | Old development MAE before → after |','|---|---:|---:|']
    for p in sorted(dest.glob('leaf-*/result.json')):
        r=json.loads(p.read_text());lines.append(f"| {r['weight']:.0f} | {r['before']['mined']:.2f} → {r['result']['metrics']['all']['model']['mae']:.2f} | {r['before']['old']:.2f} → {r['after_old_mae']:.2f} |")
    lines+=['',
    'The selected balance-3 model reduced sampled-state error but damaged the old distribution somewhat. This experiment combines extra optimization and new data; there is no matched-update replay-only leaf control. Do not attribute all improvement to data source. Stand-pat sampling is not the same as sampling capture-free terminal qsearch leaves. Full search history is not reconstructed; FEN rights/EP/halfmove are retained, and null-search branches may appear. These limitations motivate the next data design.','',
    '## Completed Linux decision screens','',
    'Twelve source variants (Tempest plus eleven candidates), 110 previously used development roots, both 200k-node and 300ms maximum allowance: **2,640 completed decision searches**. One active search per pinned CPU, at most two CPU lanes. Iterative-deepening time management can return before the allowance; these are equal allowances, not forced equal elapsed time. Teacher regret comes from already collected full legal alternatives at finite 16k-node budgets. It is a diagnostic proxy, not true minimax regret or Elo.','',
    '| Variant | Fixed-node regret (cp) | Equal-wall regret (cp) | >200cp errors, wall | Cold import (s) |','|---|---:|---:|---:|---:|']
    for name,r in result.items():lines.append(f"| {name} | {r['nodes']['clipped_500_mean']:.2f} | {r['wall']['clipped_500_mean']:.2f} | {r['wall']['mistakes_over_200']} | {r['cold_seconds']:.2f} |")
    lines+=['',
    'Regret is capped at 500cp for the predeclared aggregate, with >200cp errors reported separately. Root-paired bootstrap intervals are in `decision-results.json`; they are exploratory, unadjusted for multiple comparisons and repeated development use. No candidate cleared the frozen rule: at least 5cp better equal-wall clipped regret, no increase in >200cp errors, and no fixed-node regression. Thus no new 16/112-game match was started, and no independent confirmation openings were consumed.','',
    'Every variant passed six perft cases and fixed-node ABA reset identity. Each neural variant passed 5,288 arbitrary-position exact integer accumulator checks and output-reference checks; the contextual variant includes king-view refreshes. All cold imports were below the 80s research guard. These are Linux research gates, not a complete no-network competition certification.','',
    '## Next experiment, in priority order','',
    '1. **Train after the search decision, not before it.** Collect each root alternative\'s completed principal variation and the terminal quiet evaluation state our engine actually backed up. Label alternatives with a stronger offline search and preserve root perspective, bound type, history and depth. Fit pairwise backed-up preference/regret with replay, contrasting it with same-data static loss. Treat stand-pat cutoff states separately from settled capture-free leaves. This directly tests the target mismatch left unresolved by direct-child ranking.',
    '2. **Expand independent coverage before more epochs.** Use several thousand distinct development/training root families from separate games/openings; put transpositions and colour mirrors in the same split. Reserve fresh families before teacher collection. Mine optimistic errors and opponent refutations with fixed sampling budgets rather than just average positions. The current 64-root training sample is a pilot, not sufficient coverage.',
    '3. **Retain the 25%/50% hybrid as an integration control.** It has better fixed-node decision evidence than full replacement. Compare each new learned checkpoint at the same blend and same search policy before combining changes. Keep Tempest as the playing-strength benchmark; no Agamemnon branch has yet beaten it convincingly.',
    '4. **Only then add model capacity where decision residuals demand it.** Test a small original nonlinear layer combining mover/opponent activations, or richer threat/context features, against a matched-data/update original head. King-relative features alone did not pass this cycle. Price every architecture in equal-wall move quality, not merely prediction error.',
    '5. **Prove the finished system.** A development nominee first plays paired short games, then independent full competition-clock confirmation against Tempest with the prescribed referee and operational gates. Use confidence intervals and an effect-size target; never call a 16-game score definitive.','',
    '## Reproduction and preservation','',
    'Source: `lab/agamemnon_scale/frontier.py`, `frontier_stage.py`, `frontier_probe.py`, `frontier_extend.py`, `search_states.py`, `frontier_leafstage.py`, `frontier_summary.py`, `frontier_report.py`. Frozen native sources, parameter hashes, plans, curves, per-root results and teacher labels are in `lab/agamemnon_scale/frontier/`. The report generator requires every stream to finish and refuses a no-promotion report if a candidate meets nomination conditions.','',
    'Fourteen training fits completed: eight contextual/matched public+adaptation fits, four preference/replay fits, two mined-leaf fits. Failed collector pilot (NumPy boolean passed to python-chess) is preserved separately, fixed before successful collection; fixed-node trace on/off identity passed on two roots. A launcher path error failed before execution and was corrected. Neither touched the engine release.',
    '',
    'Current official documentation was re-fetched from [AI Chessathon docs](https://aichessathon.com/docs). Original trained weights and offline engine-labelled training are permitted; third-party engines and published chess-network weights remain excluded from submission. All transports here are research artifacts, not submission zips.','',
    f"Desktop `agent.zip` SHA256: `{sha(ROOT.parent/'agent.zip')}`. Expected Tempest hash: `0ed607e21235046d239c05d5bcb735e48b919e3d6d83cd74fe543c134addf6e4`."]
    assert sha(ROOT.parent/'agent.zip')=='0ed607e21235046d239c05d5bcb735e48b919e3d6d83cd74fe543c134addf6e4'
    report=ROOT/'docs/AGAMEMNON_FRONTIER_RESULTS.md';report.write_text('\n'.join(lines)+'\n',encoding='utf-8');print(report)
if __name__=='__main__':main()

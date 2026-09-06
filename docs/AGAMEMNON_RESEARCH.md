# Agamemnon — architecture research and working prototype

6 September 2026 · Architecture R&D, not a release recommendation

**The strongest new direction is an original learned evaluator, trained at much
larger scale, coupled to a policy that allocates search effort.** We now have a
working native neural prototype and a fast path to substantial permitted training
data. This is a credible expansion of the engine's capabilities; it is not yet a
demonstrated leap in playing strength or proof of the highest possible ceiling.

The first cycle completed **100 training fits**, Linux inference experiments,
native search integration, and an exact incremental evaluation implementation.
Desktop `agent.zip` remains the tested Tempest r1.

## What the leader evidence actually shows

At the round-39 snapshot, AlphaFish was first with **23 wins, 2 draws, 1 loss**.
Its recent opponents included Capablanca, pheanup, FuzzyBot and Sobriety. That
supports a substantial strength gap against good opposition. Public records do
not reveal its network, search depth, node rate, training data or changing agent
versions. The ladder and team page can update at different times, so their
ratings should not be combined into one snapshot.
[Official leaderboard](https://aichessathon.com/leaderboard) ·
[AlphaFish game history](https://aichessathon.com/team/659a3020-8af7-4934-b753-3b7c5fd11184?from=lb)

I downloaded and legally replayed four recent games: **679 plies**. AlphaFish
finished them with **15.63–33.90 seconds**. For moves taking over 100 ms, a simple
linear fit against the remaining bank explained **94–97%** of timing variation;
the slope was about 0.03. This resembles ordinary bank-proportional allocation.
It does not recover the algorithm: phase and bank covary, and the fit excludes
fast paths. There is no positive evidence here that elaborate importance-based
clock allocation explains the gap.

Millisecond opening moves, late forced continuations and four-piece play suggest
separate fast paths, but cannot identify books, tablebases or retained mating
lines. Useful benchmark categories are sustained king defence, material-imbalance
transitions and conversion. Spending every remaining second is not itself the
architectural objective.
[R39](https://aichessathon.com/game/be2f66e2-cb20-4800-98d1-ed488461b1d6) ·
[R38](https://aichessathon.com/game/6eaedfff-88c6-40ff-9d9e-4872aeda5661) ·
[R37](https://aichessathon.com/game/e8fd704b-a562-48cd-8f5e-b8efd9b53973) ·
[R36](https://aichessathon.com/game/a4293ded-caef-4bc3-8fa7-9a8c61be2eeb)

## The largest practical discovery: scale the data cheaply

ChessBench publishes engine-labelled positions. Its full state-value file is
38.60 billion bytes, but a range reader can fetch selected records and their
offsets without downloading the whole file. Our original reader acquired
**200,000 records in 29.8 seconds using 14.56 MB**, with fixed sample locations,
object ETag, generation, byte ranges and hashes. No published model was downloaded.
[DeepMind dataset documentation and attribution](https://github.com/google-deepmind/searchless_chess)

After filtering and exact/mirror deduplication, there are **152,163 training
positions and 19,020 development positions**. Another **20,000 raw records remain
sealed and undecoded**. The initial training sweep used nested 8k, 32k and 100k
subsets. Preparation of the numeric arrays took 231 seconds; encoding, filtering
and compression are now a material pipeline cost worth parallelizing.

The competition permits engine-labelled training data and originally trained
weights, while prohibiting third-party engine ports, published networks and
runtime engine-answer databases. It also permits shipped opening books and
tablebases. The live resource contract remains one CPU, 2 GB, 90-second import,
120 seconds plus 0.5 seconds per move, and 50 MB uncompressed submission data.
[Competition rules](https://aichessathon.com/docs/rules.md) ·
[Agent contract](https://aichessathon.com/docs/agent-contract.md)

**The data require adaptation.** A 48-position independent SF19 audit established
that the public probabilities are oriented to the player to move. Inverted public
CP and local CP correlated at 0.987; a through-zero local/public scale fit was
1.37. This is finite, different-version teacher evidence, not a universal
conversion constant. Public game positions also differ from search leaves.
Uncorrected target calibration and distribution shift are plausible transfer
bottlenecks; the experiments do not isolate their individual causal effects.

The public data lack game IDs. Blocks were separated before inspecting labels,
and exact/mirrored duplicate positions were removed. This **does not establish
opening-family independence**. The old Tempest validation and test partitions
were already inspected in earlier work; both are explicitly development data.
No result here is an untouched promotion holdout.

## What was built and measured

### Representation and training experiments

The first 60 fits crossed ten configurations with three training-family sizes
and two random seeds. They covered an additive control, nonlinear sparse
accumulators, shared king-bucket factors, king-relative geometry and factorized
piece-pair interactions. Every arm used the same recorded Tempest base score.
Colour symmetry and 72 finite-difference gradient checks passed in each worker.

On the small corpus, larger models generally benefited from more data but did not
establish superiority. The additive control reached 267.93 CP mean development
error against Tempest's 272.50; nonlinear arms mostly reached 270–274. This is a
useful control against claiming that complexity alone creates an advantage.

The next 24 fits trained original models from scratch on public data. At 100k
training positions, public development MAE was approximately **165–167 CP**,
against the PeSTO control's **179.53 CP**. The bigger networks were not uniformly
better, and selected epochs often preceded the end of training. More capacity
and longer training should therefore be experiments, not assumptions.

The final 16 fits compared random initialization with public pretraining, followed
by identical adaptation to our search-state labels:

| Architecture | Scratch → search labels | Public pretraining → search labels |
|---|---:|---:|
| Nonlinear accumulator, 32 units | 280.02 | **268.42** |
| Nonlinear accumulator, 128 units | 279.63 | **269.49** |
| Pair-interaction model, rank 32 | 285.08 | 273.65 |
| King-relative model, 32 units | 284.03 | 274.53 |

Values are CP MAE, averaged over two seeds on 1,129 reused development states.
All four transfer comparisons use the same PeSTO base and fine-tuning budget.
Tempest's recorded evaluator is **272.50** on those same states. This is evidence
that pretraining helps these models, not a chess Elo estimate.

There are material weaknesses: the 32-unit model does not consistently improve
quiet-state or tail errors. One seed's quiet-state 90th-percentile error rose
from 438 to 461 CP. The isolated public-pretraining controls, base changes,
different teacher versions and reused development set must remain visible.

### Native evaluation and search

A 32-unit model now runs inside the existing verified legal/search machinery.
Weights are explicit numeric arguments through recursion, avoiding giant learned
arrays embedded in JIT code. This bridge compiled in **34.50 seconds** on Linux
and passed six perft positions, evaluation parity and twelve legal wall-budget
root probes. It changes evaluation, not merely a pruning constant.

The next implementation uses an **exact lazy feature cache**. It stores the last
evaluated board and integer feature sums. At the next evaluation, bitboard
differences remove departed pieces and add arrivals, even after arbitrary search
jumps. It does not assume that the previous evaluation was the current node's
parent. Side-only changes need no piece update. Integer sums avoid drift from
millions of floating-point additions and subtractions.

Quantizing its features at scale 4096 changed predictions by **0.093 CP on
average**, at most **0.488 CP**, across 5,288 positions. Output weights retain
their trained float values. Both the quantized refresh control and incremental
version passed all 5,288 evaluation comparisons; the incremental version also
matched independently rebuilt feature sums exactly on every position.

Two Linux runs with VPS core assignments swapped produced **24 identical
fixed-node comparisons**: move, score, depth and node count all matched. The
incremental version was approximately **9.8% faster geometrically** than its
matching refresh control. This is six selected diagnostic roots, not a universal
throughput gain or an Elo claim. Full-search imports measured roughly 34–36
seconds. Separate random-weight kernel tests covered 18 configurations and
10,791 update/undo transitions, including special moves.

The neural bridge still chooses `Qxa5` in the existing round-37 diagnostic. It has
not solved the tactical weakness merely by adding a network. There are no new
full-clock strength matches or promotion recommendation from this cycle.

### A different search-allocation building block

An original probability-depth allocator is implemented and tested. Uniform move
probabilities consume one depth unit; minimum cost prevents zero-cost cycles,
and a uniform mixture can preserve probability on every legal branch. Calibration
on 4,064 reused quiet-move groups reduced descriptive log loss from about 3.15
for uniform probabilities to 2.72.

However, roughly **one third of teacher moves still receive less probability than
uniform allocation**. This cannot safely become an unverified branch filter.
Current labels also omit capture alternatives, preference margins and tactical
refutations. The allocator is a building block; it is not integrated into the
playing prototype.

## Architecture choices still worth pursuing

| Lane | What changes structurally | Next experiment that can distinguish it |
|---|---|---|
| Incremental learned evaluation | Replaces a small fixed feature correction with learned interactions | More representative search-state data; width × data scaling; actual decision regret and equal-wall search |
| Learned probability-budget alpha-beta | Policy controls effort across branches, beyond ordering ties | Ordering-only versus probability budgets; calibrated full-move targets; compulsory tactical verification |
| Relational policy/value advisor | A richer graph or relational model is called only where its cost can pay back | Root/upper-tree inference including feature construction; saved descendant work per microsecond |
| Best-first minimax with AB verification | Explicit frontier expansion replaces uniform iterative depth as the outer search | Cross evaluator quality × search architecture; bounded memory and complete draw state |
| Two-speed evaluation/controller | Predicts whether to spend on a richer evaluation, depth or alternative verification | Oracle gate, learned gate and equally costly simple gates on search trajectories |
| Policy/value MCTS or searchless model | Most knowledge is learned offline; search is guided by policy/value | Small original model's CPU latency and tactical regret across data scales before a large training commitment |

These are not equivalent implementation bets. Incremental evaluation is the
nearest deployable lane; richer advisors and best-first search remain higher-risk
architecture experiments. A full searchless transformer is retained as a research
comparison, but the strongest published result required vastly more data and
parameters than these pilots. It is not evidence that our small model can replace
search today.

The primary literature supports this ordering while imposing important limits:

- **Giraffe** directly studied learned evaluation and probability-limited chess
  search. Its policy improvement shrank when inference cost was included; gating
  the policy to costly nodes mattered. Our earlier quiet-history tie breaker did
  not test that architecture.
  [Matthew Lai, 2015](https://arxiv.org/pdf/1509.01549)
- **ChessBench's transformer study** showed strong scaling, but action-value
  superiority over state-value largely disappeared when data counts were
  equalized. Compare targets under equal label compute, and include alternatives
  rather than treating one-hot imitation as the only policy objective.
  [Ruoss et al., NeurIPS 2024](https://arxiv.org/html/2402.04494v2)
- **Graph chess research** reported faster initial learning than its simplified
  CNN baseline. It used multiple GPUs and one seed per configuration; the result
  was not a tenfold CPU inference improvement.
  [Rigaux and Kashima, NeurIPS 2024](https://arxiv.org/html/2410.23753v1)
- **Best-first minimax** research found pure best-first could lose its advantage
  at greater depths, while an AB hybrid performed better in its tested domains.
  Those were not modern chess-engine comparisons.
  [Korf and Chickering, 1996](https://www.maxchickering.com/publications/aij96.pdf)
- **Minimax Strikes Back** motivates training from internal backed-up states,
  not only played roots. Its reported data-yield gains do not mean equally many
  independent examples or corresponding chess Elo.
  [Cohen-Solal and Cazenave, AAMAS 2023](https://www.lamsade.dauphine.fr/~cazenave/papers/MinimaxStrikesBack_AAMAS.pdf)
- **Computation-selection theory** warns that a superficially stable decision can
  still need several computations before a useful reversal becomes visible.
  [Hay et al., UAI 2012](https://arxiv.org/pdf/1408.2048)

## Decision and next build

Advance the **original incremental neural evaluator plus learned search-allocation
research** as Agamemnon's primary path. Retain graph-advisor and best-first arms
as architectural alternatives. Do not promote the present neural prototype on
its scalar error: quiet/tail regressions, decision quality and full-clock playing
strength remain unresolved.

The next implementation sequence is specified in `AGAMEMNON_BUILD_SPEC.md`:
scale and balance search-relevant training; test richer targets and evaluator
capacity; collect alternative/refutation labels; integrate policy allocation with
mandatory verification; compare architecture/evaluator combinations at equal
wall time. Only then use independent full-clock strength confirmation.

Round 40 versus PawnStorm arrived after these fits and checkpoint selection. It
was a legal 142-ply threefold draw with 4.006 seconds left for our side. It is
registered as a new diagnostic, not used to fit these models or independently
reference-reviewed here.

Reproduction and raw evidence are in `lab/agamemnon/`: immutable training streams,
source/checkpoint hashes, public byte-range manifests, source transports, native
gate logs, `leader-evidence.json` and audited `results.json`. No published network,
runtime answer database or new release archive was produced. Markdown structure
and links were checked; no separate paginated rendering was performed.

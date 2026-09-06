# Agamemnon: architecture discovery

Started 6 September 2026. This is an isolated research generation, authorized by
the user's explicit reopening of architecture choices. Tempest r1 is the control.
No change to Desktop agent.zip is implied by a pilot result.

## Questions and evidence

1. Establish current competition constraints and leader evidence from official
   rules, contract, team pages and games. A record cannot identify implementation.
2. Compare learned representations and search structures using primary papers.
   Two independent architecture research lanes and one opponent evidence lane.
3. Run original representation/capacity/data-size experiments, with frozen family
   splits and source hashes. Previously inspected validation/test data are
   development diagnostics, never a fresh strength holdout.
4. Measure original kernels on Linux x86_64, one CPU and one thread. Separate
   isolated inference from whole-search throughput and cold agent initialization.
5. Synthesize evidence, uncertainty and a ranked build specification. Select on
   scaling, decision quality and cost; an immature model's first match is not a
   ceiling estimate. Preserve all attempted configurations and failures.

## Initial experimental arms

- Additive learned piece-square residual: representation control.
- Shared sparse accumulator with nonlinear output: 32/128/256 capacity sweep.
- Shared piece factors plus king-bucket factors: context without fragmenting all
  training across independent king buckets.
- King-relative piece geometry plus absolute piece factors: relational sharing.
- Factorized pair interactions: learns piece-pair effects with incremental sums.
- Policy-shaped alpha-beta and best-first minimax: researched independently;
  implement after inspecting cost and target requirements.

Use 25%, 50%, 100% of training families, two seeds, identical validation groups.
Include quiet-state and tactical-guard errors separately. No tactical proof is
claimed from a static evaluator. Scalar pilots precede move-ranking/search tests.
Keep the twelve existing fresh confirmation opening families unused.

## Selection and stopping

Keep the Pareto frontier of validation error, tail errors, parameter bytes and
one-core inference costs, including arms whose learning curve is still improving.
Use both data scaling and capacity scaling; do not infer a power law from three
small points. Keep label-quality and representation experiments distinct.
Deployment later requires current-referee semantics, incremental-state parity,
full-search runtime, Linux import/protocol and independent full-clock matches.

No update_plan tool is available in this session; this file records the plan.
Completed: official source audit, three bounded research lanes,60 representation
fits,24 public-data fits,16 transfer fits, policy-budget calibration, Linux kernel
and native search integration, exact lazy-delta feature cache, counterbalanced
timing, source/stream audit and synthesis. See results.json and
../../docs/AGAMEMNON_RESEARCH.md. No training/test service remains active.

Follow-up questions (not claims answered by this cycle): full-clock strength,
quiet/tail improvements, learned allocation integration, richer policy/value
advisors and best-first architecture/evaluator comparisons. Existing Tempest
release remains unchanged.

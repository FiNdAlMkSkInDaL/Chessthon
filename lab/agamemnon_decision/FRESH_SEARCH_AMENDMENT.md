# Fixed-snapshot fresh-search comparison

The first objective rounds all selected the unchanged initial function under
the frozen-PV regret metric (except small replay-control gains). That selector
does not test changed search trees and could reject an improvement prematurely.

Before seeing fresh-search results, nominate the **fixed epoch-64 snapshot** of
each primary-seed soft-round objective and each residual-head objective, at
both 25% and 50% mixing. These are diagnostic nominees irrespective of the
frozen-PV checkpoint-selection outcome or old static MAE. Do not replace the
best-known checkpoint with these snapshots merely because they were staged.

Snapshot runs replay the same initialization, data, seed, update sequence and
objective as the earlier completed soft-round fits; saving fixed epochs is the
only change. They are repeated optimization runs, not six independent new fits.
Save epochs 16, 64 and 128 for reproducibility, but only epoch 64 enters this
fresh-search cohort. This change does not lower the Linux decision nomination
rule, playing-strength gates or release requirements.

The soft round itself used >=5cp pairs, teacher soft probabilities at 120cp
temperature, 128 epochs, learning rate 0.0005 and replay gradient weight 0.25.
Hard-round runs used >=40cp pairs, 16 epochs, 0.00015 and replay weight 1.
These are multi-parameter experiment rounds. Within each round the objective
arms and controls have matched data, update schedules and seeds; differences
between rounds cannot be attributed to preference softness alone.

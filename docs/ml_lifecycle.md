# ML Lifecycle

> Required by the spec to be complete **before Phase 3 sign-off**. Defines the target, features,
> baseline, metrics, registry, and retraining/drift policy.

## Problem definition

- **Task:** binary classification — predict **P(home team wins)** for a scheduled game.
- **Output:** a calibrated probability in `[0,1]`; the implied pick is `home` if `p ≥ 0.5` else
  `away`. See [`decisions.md`](./decisions.md) D-002.
- **Label:** `1` if the home team won the completed game, else `0` (from `games` final scores).

## Data

- **Source:** PostgreSQL only (`games`, derived `team_stats`, derived `standings`) — never the live
  provider. `collect` reads what ETL has already landed.
- **Window:** rolling last N seasons (default 5) of completed regular-season games.
- **Split:** time-based (train on earlier seasons, evaluate on the most recent) to avoid leakage —
  no random shuffling across time.

## Features (all derivable from free `games` data — no paid tier)

- Rolling team form: win % and average point differential over each team's last 10 games.
- Rest days since each team's previous game; back-to-back flag.
- Season-to-date net rating (points for − against per game).
- Home/away indicator.
- Head-to-head record this season.

`clean` and `feature_engineering` are pure functions, unit-tested on small fixture frames.

## Baseline

- **Majority class:** predict home win for every game (~57–58% historically). Defined once in
  `/ml/pipeline/baseline.py`. A candidate model must beat baseline on **both** accuracy and log loss
  on the held-out set before it is eligible for registration (D-003, spec requirement).

## Models

- Start: **logistic regression** (interpretable, fast, well-calibrated).
- Upgrade: **gradient boosting** (sklearn `HistGradientBoostingClassifier`).
- CPU-only, pickle-serializable, no GPU — keeps the $0 budget.

## Evaluation (logged every run, win or lose)

- **Accuracy**, **log loss**, and **calibration** (Brier score + reliability-curve summary).
- Every training run appends metrics to the run log so rejected candidates are recorded too.

## Registry & promotion

- Artifacts: `/ml/models/model_v{n}_{date}.pkl`.
- `registry.json` entry per version: metrics, training-data window, feature list, git commit hash,
  and an `active` pointer.
- **Registration** happens only if the candidate beats baseline. **Training does not auto-activate**
  — flipping `active` is an explicit, separate promotion step.

## Inference (in the API)

- The API loads the `active` model at **process startup** and via a **manual reload** endpoint/
  signal — never per-request, never retrain-on-request, never load-on-demand. Bounded `/model/predict`
  latency, independent of training code (design §1/§6).

## Retraining cadence & drift trigger (resolves the last open ML decision)

- **Cadence:** weekly retrain (scheduled), since new completed games accumulate daily.
- **Drift trigger:** if the trailing-30-game **Brier score** of the active model degrades by more
  than **20%** relative to its registered evaluation Brier, flag for retrain/repromotion. Computed
  from settled `model_predictions` (see D-008 grading job).
- **Promotion policy:** a freshly trained model is promoted to `active` only if it beats **both** the
  current active model and the baseline on the latest held-out window.

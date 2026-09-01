import type { PlayerInsight } from "../api/types";

export interface InsightBadge {
  label: string;
  className: string;
}

const WIN_BADGE = "text-win ring-win/40";
const LOSS_BADGE = "text-loss ring-loss/40";

/**
 * Maps an insight to its display label and colour.
 *
 * `regression_signal`'s score is signed, and the sign is meaningful: a POSITIVE score means the
 * player is shooting above their own baseline and is likely to decline ("regression", shown in
 * loss red), while a NEGATIVE score means they are shooting below baseline and are a bounce-back
 * candidate likely to improve ("bounce-back", shown in win green). Breakout insights are always
 * framed as good news.
 */
export function insightBadge(insight: Pick<PlayerInsight, "kind" | "score">): InsightBadge {
  if (insight.kind === "breakout") {
    return { label: "breakout", className: WIN_BADGE };
  }
  return insight.score < 0
    ? { label: "bounce-back", className: WIN_BADGE }
    : { label: "regression", className: LOSS_BADGE };
}

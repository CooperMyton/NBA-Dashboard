/**
 * Formats one stat cell for a player table: one decimal place, or an em dash when the player has
 * no stat line. Shared by the Players page and the team roster so the two tables never drift.
 */
export function statCell(value: number | undefined, digits = 1): string {
  return value === undefined ? "—" : value.toFixed(digits);
}

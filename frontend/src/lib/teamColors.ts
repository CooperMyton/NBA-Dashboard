// Primary team colors by abbreviation — used to color-code the UI so it feels like real
// basketball, not a generic template.
export const TEAM_COLORS: Record<string, string> = {
  ATL: "#E03A3E",
  BOS: "#007A33",
  BKN: "#1A1A1A",
  CHA: "#00788C",
  CHI: "#CE1141",
  CLE: "#860038",
  DAL: "#0053BC",
  DEN: "#0E2240",
  DET: "#C8102E",
  GSW: "#1D428A",
  HOU: "#CE1141",
  IND: "#FDBB30",
  LAC: "#C8102E",
  LAL: "#552583",
  MEM: "#5D76A9",
  MIA: "#98002E",
  MIL: "#00471B",
  MIN: "#236192",
  NOP: "#B4975A",
  NYK: "#F58426",
  OKC: "#007AC1",
  ORL: "#0077C0",
  PHI: "#006BB6",
  PHX: "#E56020",
  POR: "#E03A3E",
  SAC: "#5A2D81",
  SAS: "#9EA2A2",
  TOR: "#CE1141",
  UTA: "#2B5134",
  WAS: "#C8102E",
};

export function teamColor(abbr: string | undefined | null): string {
  if (abbr && TEAM_COLORS[abbr]) return TEAM_COLORS[abbr];
  return "#ff7a45";
}

import { describe, expect, it } from "vitest";

import { formatPct, formatSeason } from "./format";

describe("format helpers", () => {
  it("formats percentages", () => {
    expect(formatPct(0.625)).toBe("62.5%");
    expect(formatPct(1)).toBe("100.0%");
  });

  it("formats an NBA season from its start year", () => {
    expect(formatSeason(2023)).toBe("2023-24");
    expect(formatSeason(1999)).toBe("1999-00");
  });
});

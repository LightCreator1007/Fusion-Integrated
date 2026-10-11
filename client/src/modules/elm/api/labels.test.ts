import { describe, expect, it } from "vitest";

import { awaitingLabel, formatDays, formatPeriod, outcomesFor } from "./labels";

describe("outcomesFor", () => {
  it("offers a substitute consent, not approval", () => {
    expect(outcomesFor("consent")).toEqual(["accepted", "declined"]);
  });

  it("lets the Unit Head record a recommendation rather than reject", () => {
    expect(outcomesFor("recommend")).toEqual(["recommended", "not_recommended"]);
  });

  it("lets Establishment only forward, and the final step decide", () => {
    expect(outcomesFor("forward")).toEqual(["forwarded"]);
    expect(outcomesFor("final")).toEqual(["approved", "rejected"]);
  });
});

describe("formatting", () => {
  it("drops the decimal on whole days and keeps half days", () => {
    expect(formatDays("3.00")).toBe("3");
    expect(formatDays("0.50")).toBe("0.5");
  });

  it("names a half-day request's half", () => {
    expect(formatPeriod("2026-03-09", "2026-03-09", "first")).toContain("first half");
    expect(formatPeriod("2026-03-09", "2026-03-12", "")).toContain(" to ");
  });

  it("shows an unknown authority as the server sent it", () => {
    expect(awaitingLabel("registrar")).toBe("Registrar");
    expect(awaitingLabel("someone_new")).toBe("someone_new");
  });
});

import { describe, expect, it } from "vitest";
import { parseOrchestrationSummary, previewText } from "./callCrmSummary";

describe("parseOrchestrationSummary", () => {
  it("parses xfer and disp tails", () => {
    const s = "Booking ok | orch_lead={\"caller_name\":\"Ada\"} | disp=booking_confirmed | xfer=requested";
    const p = parseOrchestrationSummary(s);
    expect(p.baseSummary).toBe("Booking ok");
    expect(p.orchLead).toEqual({ caller_name: "Ada" });
    expect(p.disposition).toBe("booking_confirmed");
    expect(p.transferStatus).toBe("requested");
  });

  it("handles missing orch segment", () => {
    const s = "Done | disp=completed | xfer=none";
    const p = parseOrchestrationSummary(s);
    expect(p.baseSummary).toBe("Done");
    expect(p.orchLead).toBeNull();
    expect(p.disposition).toBe("completed");
    expect(p.transferStatus).toBe("none");
  });

  it("guards malformed JSON", () => {
    const s = "x | orch_lead={oops | disp=completed | xfer=fail";
    const p = parseOrchestrationSummary(s);
    expect(p.orchLead).toBeNull();
    expect(p.disposition).toBe("completed");
  });
});

describe("previewText", () => {
  it("handles empty", () => {
    expect(previewText("")).toBe("");
    expect(previewText("unavailable")).toBe("");
  });
});

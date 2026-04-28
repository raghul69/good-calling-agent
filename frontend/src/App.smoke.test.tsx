import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "./App";

/** Import + mount graph (jsdom). Failures here mirror blank-page import/render crashes. */
describe("App smoke", () => {
  it("imports and renders landing without throwing", async () => {
    render(<App />);
    expect(await screen.findByRole("navigation")).toBeInTheDocument();
  });
});

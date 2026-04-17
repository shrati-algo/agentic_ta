import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { KpiDonut } from "../../src/components/KpiDonut";

describe("KpiDonut", () => {
  it("renders the legend with the status labels from labels.ts", () => {
    render(<KpiDonut pass={44} review={35} fail={8} violationPct={9.2} />);
    expect(screen.getByText("Okay")).toBeInTheDocument();
    expect(screen.getByText("Somewhat Okay")).toBeInTheDocument();
    expect(screen.getByText("Not Okay")).toBeInTheDocument();
  });

  it("renders the legend counts", () => {
    render(<KpiDonut pass={44} review={35} fail={8} violationPct={9.2} />);
    expect(screen.getByText("44")).toBeInTheDocument();
    expect(screen.getByText("35")).toBeInTheDocument();
    expect(screen.getByText("8")).toBeInTheDocument();
  });

  it("renders the centre violation percentage", () => {
    render(<KpiDonut pass={44} review={35} fail={8} violationPct={9.2} />);
    expect(screen.getByText("9.20%")).toBeInTheDocument();
  });

  it("renders the total", () => {
    render(<KpiDonut pass={10} review={5} fail={3} violationPct={42} />);
    const totalLine = screen.getByText(/Total:/);
    expect(totalLine.textContent).toContain("18");
  });
});

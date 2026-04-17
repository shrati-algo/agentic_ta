import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatusPill } from "../../src/components/StatusPill";

describe("StatusPill", () => {
  it("renders the Okay label for PASS", () => {
    render(<StatusPill status="PASS" />);
    expect(screen.getByText("Okay")).toBeInTheDocument();
  });

  it("renders the Somewhat Okay label for REVIEW", () => {
    render(<StatusPill status="REVIEW" />);
    expect(screen.getByText("Somewhat Okay")).toBeInTheDocument();
  });

  it("renders the Not Okay label for FAIL", () => {
    render(<StatusPill status="FAIL" />);
    expect(screen.getByText("Not Okay")).toBeInTheDocument();
  });

  it("renders the Error label for ERROR", () => {
    render(<StatusPill status="ERROR" />);
    expect(screen.getByText("Error")).toBeInTheDocument();
  });

  it("has the right accessible name", () => {
    render(<StatusPill status="FAIL" />);
    expect(screen.getByRole("status")).toHaveAccessibleName("Not Okay");
  });

  it("uses distinct colour classes per status", () => {
    const { rerender } = render(<StatusPill status="PASS" />);
    const passClass = screen.getByRole("status").className;

    rerender(<StatusPill status="REVIEW" />);
    const reviewClass = screen.getByRole("status").className;

    rerender(<StatusPill status="FAIL" />);
    const failClass = screen.getByRole("status").className;

    expect(passClass).not.toBe(reviewClass);
    expect(reviewClass).not.toBe(failClass);
    expect(passClass).toContain("green");
    expect(reviewClass).toContain("amber");
    expect(failClass).toContain("red");
  });
});

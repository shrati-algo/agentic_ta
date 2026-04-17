import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CameraCard } from "../../src/components/CameraCard";
import type { ChassisPerCamera } from "../../src/api/types";

const sample: ChassisPerCamera = {
  measurement_id: "abc12345-1234-1234-1234-1234567890ab",
  diameter_mm: 47.315,
  status: "PASS",
  confidence: 0.94,
  debug_image_url: "/v1/debug/abc12345",
};

describe("CameraCard", () => {
  it("shows the camera label and the status pill when a measurement is present", () => {
    render(
      <CameraCard
        side="L"
        camera={sample}
        operatorDecision={null}
        onDecision={() => {}}
      />
    );
    expect(screen.getByText("Cam1")).toBeInTheDocument();
    expect(screen.getByText("Okay")).toBeInTheDocument();
    expect(screen.getByText(/47.315/)).toBeInTheDocument();
  });

  it("renders a placeholder when no measurement", () => {
    render(
      <CameraCard
        side="R"
        camera={null}
        operatorDecision={null}
        onDecision={() => {}}
      />
    );
    expect(screen.getByText(/No image for Cam2/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Correct Violation" })).toBeDisabled();
  });

  it("fires onDecision when a button is clicked", () => {
    const onDecision = vi.fn();
    render(
      <CameraCard
        side="L"
        camera={sample}
        operatorDecision={null}
        onDecision={onDecision}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: "Correct Violation" }));
    expect(onDecision).toHaveBeenCalledWith("CORRECT");
    fireEvent.click(screen.getByRole("button", { name: "Incorrect Violation" }));
    expect(onDecision).toHaveBeenCalledWith("INCORRECT");
  });

  it("highlights the selected decision", () => {
    render(
      <CameraCard
        side="L"
        camera={sample}
        operatorDecision="CORRECT"
        onDecision={() => {}}
      />
    );
    const correctBtn = screen.getByRole("button", { name: "Correct Violation" });
    expect(correctBtn.className).toContain("bg-green-600");
  });
});

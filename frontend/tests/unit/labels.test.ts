import { describe, expect, it } from "vitest";

import { CAMERA_LABEL, STATUS_LABEL, cameraLabel, statusLabel } from "../../src/labels";

describe("labels mapping (TRD 10.3)", () => {
  it("maps every backend status to its UI label", () => {
    expect(STATUS_LABEL.PASS).toBe("Okay");
    expect(STATUS_LABEL.REVIEW).toBe("Somewhat Okay");
    expect(STATUS_LABEL.FAIL).toBe("Not Okay");
    expect(STATUS_LABEL.ERROR).toBe("Error");
  });

  it("maps camera sides to Cam1 / Cam2", () => {
    expect(CAMERA_LABEL.L).toBe("Cam1");
    expect(CAMERA_LABEL.R).toBe("Cam2");
  });

  it("statusLabel / cameraLabel helpers agree with the constants", () => {
    expect(statusLabel("PASS")).toBe(STATUS_LABEL.PASS);
    expect(cameraLabel("R")).toBe(CAMERA_LABEL.R);
  });
});

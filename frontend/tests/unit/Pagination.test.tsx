import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Pagination } from "../../src/components/Pagination";

describe("Pagination", () => {
  it("renders page/of/total", () => {
    render(
      <Pagination
        page={2}
        pageSize={10}
        total={87}
        onPageChange={() => {}}
      />
    );
    expect(screen.getByText(/2 of 9/)).toBeInTheDocument();
  });

  it("disables prev on first page", () => {
    render(
      <Pagination page={1} pageSize={10} total={30} onPageChange={() => {}} />
    );
    expect(screen.getByLabelText("previous page")).toBeDisabled();
  });

  it("disables next on last page", () => {
    render(
      <Pagination page={3} pageSize={10} total={30} onPageChange={() => {}} />
    );
    expect(screen.getByLabelText("next page")).toBeDisabled();
  });

  it("fires onPageChange", () => {
    const onPageChange = vi.fn();
    render(
      <Pagination page={2} pageSize={10} total={30} onPageChange={onPageChange} />
    );
    fireEvent.click(screen.getByLabelText("next page"));
    expect(onPageChange).toHaveBeenCalledWith(3);
    fireEvent.click(screen.getByLabelText("previous page"));
    expect(onPageChange).toHaveBeenCalledWith(1);
  });
});

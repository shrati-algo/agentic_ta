import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { Header } from "../../src/components/Header";

describe("Header", () => {
  it("renders the nav tabs", () => {
    render(
      <MemoryRouter>
        <Header />
      </MemoryRouter>
    );
    expect(screen.getByText("Home")).toBeInTheDocument();
    expect(screen.getByText("Live View")).toBeInTheDocument();
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });

  it("shows Live when connected + session is active", () => {
    render(
      <MemoryRouter>
        <Header connected sessionId="abc" />
      </MemoryRouter>
    );
    expect(screen.getByText("Live")).toBeInTheDocument();
  });

  it("shows Reconnecting when disconnected + session exists", () => {
    render(
      <MemoryRouter>
        <Header connected={false} sessionId="abc" />
      </MemoryRouter>
    );
    expect(screen.getByText("Reconnecting")).toBeInTheDocument();
  });

  it("hides the live indicator when no session", () => {
    render(
      <MemoryRouter>
        <Header />
      </MemoryRouter>
    );
    expect(screen.queryByText("Live")).not.toBeInTheDocument();
    expect(screen.queryByText("Reconnecting")).not.toBeInTheDocument();
  });
});

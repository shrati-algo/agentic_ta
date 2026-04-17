import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        status: {
          pass: "#16a34a",
          review: "#f59e0b",
          fail: "#dc2626",
          error: "#6b7280",
        },
      },
    },
  },
  plugins: [],
} satisfies Config;

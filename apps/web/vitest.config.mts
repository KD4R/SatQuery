import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    // Playwright owns e2e/; vitest owns unit and contract tests beside their modules.
    include: ["lib/**/*.test.ts", "components/**/*.test.ts"],
    environment: "node",
  },
});

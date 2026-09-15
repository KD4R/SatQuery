import { FlatCompat } from "@eslint/eslintrc";

/**
 * ESLint flat config (P5-16).
 *
 * The repo lints Python with flake8 and black but had no JavaScript linter at all.
 * The `lint` script pointed at `next lint`, which in Next 15.5 is deprecated and,
 * with no config present, drops into an interactive setup prompt — so it hung
 * rather than failing, which is the worst way for a check to be broken.
 *
 * This is the flat config `next lint` would have generated, committed so the check
 * is reproducible and non-interactive.
 */

const compat = new FlatCompat({ baseDirectory: import.meta.dirname });

const config = [
  {
    ignores: [
      ".next/**",
      "node_modules/**",
      "public/**",
      "playwright-report/**",
      "test-results/**",
      "next-env.d.ts",
    ],
  },

  ...compat.extends("next/core-web-vitals", "next/typescript"),

  {
    rules: {
      // The console is full of deliberate NOT AVAILABLE paths where a value is
      // legitimately absent; `any` is not how they are expressed, so keep this on.
      "@typescript-eslint/no-explicit-any": "error",

      // Error boundaries log to console on purpose — there is no telemetry sink in
      // the gateway contract yet. Warn everywhere else.
      "no-console": ["warn", { allow: ["warn", "error"] }],

      // Unused args prefixed with _ are intentional (signature conformance).
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
    },
  },
];

export default config;

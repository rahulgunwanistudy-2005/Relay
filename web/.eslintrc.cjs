module.exports = {
  root: true,
  env: { browser: true, es2021: true },
  parser: "@typescript-eslint/parser",
  parserOptions: { ecmaVersion: "latest", sourceType: "module" },
  plugins: ["@typescript-eslint", "react-hooks"],
  extends: [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
  ],
  settings: {},
  rules: {
    "react-hooks/rules-of-hooks": "error",
    "react-hooks/exhaustive-deps": "warn",
    "@typescript-eslint/no-unused-vars": ["warn", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }],
    "@typescript-eslint/no-explicit-any": "off",
    "no-empty": ["warn", { allowEmptyCatch: true }],
  },
  ignorePatterns: ["dist", "node_modules", ".eslintrc.cjs", "vite.config.ts"],
};

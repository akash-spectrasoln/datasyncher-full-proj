import prettierConfig from "eslint-config-prettier";
import checkFile from "eslint-plugin-check-file";
import prettierPlugin from "eslint-plugin-prettier";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";
import tseslint from "typescript-eslint";

import prettierRules from "./.prettierrc.cjs";
import js from "@eslint/js";

export default tseslint.config(
  { ignores: ["dist"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
      prettier: prettierPlugin,
      "check-file": checkFile,
    },
    rules: {
      "@typescript-eslint/no-unused-vars": "off",
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": [
        "warn",
        { allowConstantExport: true },
      ],
      "prefer-const": "error",
      eqeqeq: ["error", "always"],
      "no-unused-expressions": "error",
      "no-duplicate-imports": "error",
      "no-unused-vars": [
        "error",
        {
          argsIgnorePattern: "^_",
          varsIgnorePattern: "^_",
        },
      ],
      "no-console": ["warn", { allow: ["warn", "error"] }],
      "no-trailing-spaces": "error",
      "no-multiple-empty-lines": "error",
      "prettier/prettier": ["error", prettierRules],
      "check-file/filename-naming-convention": [
        "error",
        {
          "src/*.{tsx}": "PASCAL_CASE",
          "src/*.{js,ts}": "KEBAB_CASE",
        },
        {
          ignoreMiddleExtensions: true,
        },
      ],
    },
  },
  {
    files: [
      "src/components/dashboard/components/Connectors/components/ConnectorDetails/components/Tabs/Schema/TransformModal/**/*.{ts,tsx}",
      "src/components/ui/ConfirmDialog.tsx",
      "src/components/ui/confirm.tsx",
    ],
    rules: {
      "no-alert": "error",
    },
  },
  prettierConfig,
);

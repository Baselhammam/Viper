// ESLint config (flat-config format). `npm run lint` runs this over the repo to
// catch bugs that `tsc` can't — tsc proves types are sound, ESLint flags suspect
// runtime patterns (misused React Hooks, dead code, etc.). It already caught two
// real issues in this codebase: a ref read during render in App.tsx and an
// unnecessary escape in injectClickScript.ts.
import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  // Build output isn't ours to lint.
  { ignores: ['dist'] },
  {
    // Baseline JS rules + the TypeScript-aware rule set, applied to all source.
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2020,
      // App code runs in the browser, so assume browser globals (window, document…).
      globals: globals.browser,
    },
    plugins: {
      // react-hooks: enforces the Rules of Hooks (correct call order, exhaustive deps).
      'react-hooks': reactHooks,
      // react-refresh: warns about patterns that break Fast Refresh during dev.
      'react-refresh': reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
    },
  },
  {
    // Config and test files run under Node, not the browser, so swap in Node globals
    // (process, etc.) — otherwise ESLint would flag them as undefined.
    files: ['vite.config.ts', 'vitest.config.ts', '**/*.test.ts'],
    languageOptions: { globals: globals.node },
  },
)

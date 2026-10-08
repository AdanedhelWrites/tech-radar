// ESLint flat config (2026-10-08). CI "Frontend (Vite build)" isi build'den once `npm run lint` kosar.
// react-hooks 7'nin React Compiler tabanli kurallari (immutability, set-state-in-effect...)
// bilincli olarak acilmadi: alti bilesen "useEffect once, fonksiyon sonra" kalibinda ve bu
// kalip calisiyor; yalniz klasik iki kural (rules-of-hooks, exhaustive-deps) uygulanir.
import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'

export default [
  { ignores: ['dist', 'node_modules'] },
  js.configs.recommended,
  {
    files: ['**/*.{js,jsx}'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      globals: globals.browser,
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    plugins: { 'react-hooks': reactHooks, 'react-refresh': reactRefresh },
    rules: {
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
      // JSX'te kullanilan bilesen/ikon adlari buyuk harfle baslar; onlari "kullanilmamis" sayma
      'no-unused-vars': ['error', { varsIgnorePattern: '^[A-Z_]', argsIgnorePattern: '^_', caughtErrors: 'none' }],
    },
  },
]

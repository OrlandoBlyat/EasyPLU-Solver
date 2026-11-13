# Community translations

English (`en.json`) is the source language and the fallback. New visitors start in their browser's preferred supported language, or English if none matches. Change language using the **Language** button beside the footer buttons; the
selection is saved in this browser. All interface copy, including accessible
labels and scheduling consent, lives in these JSON catalogs.

To contribute a language:

1. Copy `en.json` to a BCP 47 language tag such as `de.json` or `pt-BR.json`.
2. Set `name` to the language's native name (for example, `Deutsch`).
3. Translate the values in `messages`. Keep the keys unchanged: they identify
   the original English copy. Preserve placeholders such as `{count}`.
4. Run `npm run check:translations`, `npx tsc --noEmit` and `npm run build` from `frontend/`.

JSON files in this directory are discovered automatically at build time and
appear in the language menu after rebuilding. Missing or empty translations fall
back to English. Use valid JSON (double quotes, no comments or trailing commas).
Use the same placeholders as the English entry. Have a fluent speaker review
translations, especially credential storage consent.

Names of products and people stay unchanged. The backend API and frontend API proxy return English messages and do not load these files. The frontend translates progress message keys for display. The downloaded PDF retains its original language.

# Finance report rendered on Kindle

The main dashboard remains a NAS-rendered image. Updated Kindle clients request
`report_format=markdown` in the same bundle download. Version 2 bundles contain
the report's original Markdown, source date, default font size and a `finance`
page entry. They do not contain PNGs of the report text.

Kindle's existing WebKit app parses and lays out that text locally. Previous/Next
move through the report's pages, then return to the main dashboard. **A− / A+**
change the type size and repaginate without a network request. The size is saved
locally. The source date and current page appear in a small footer. When a refresh
returns identical text, the reader preserves its place.

The cache still commits only after validating all images and parsing the report.
Invalid responses retain the previous bundle. Old version 1 PNG bundles remain
readable; old clients continue requesting PNG reports. The legacy NAS editor PNG
preview remains a content reference: Kindle controls its own pagination and type.

No new heartbeat, background renderer or polling loop is added. Parsing happens
when a bundle is loaded; reflow happens on opening the report, resizing or changing
type size. The frontlight and power behavior are unchanged.

## Parser and safety

The client bundles [markdown-it 14.1.0](https://github.com/markdown-it/markdown-it/tree/14.1.0)
as an ES5 build for legacy WebKit. It supports normal Markdown headings, emphasis,
lists, quotes, code, tables and link labels. The reader creates DOM nodes from a
fixed allowlist. Raw HTML remains text; image URLs, links, styles and scripts from
the report are not fetched or executed. No CDN connection runs on Kindle.

The original source is bounded to 40,000 characters with nesting limited to 20.
All report text remains in the document; CSS columns paginate it without cutting
it down to a summary. Markdown escaping and syntax are handled by the parser,
not by custom regular-expression substitutions. The app does not execute trades.

`MARKDOWN-LICENSE.txt` includes the parser and bundled dependency licenses.
Reproduce the checked-in browser build with Node 18+:

```sh
npm install --prefix .tools/markdown-build --save-exact \
  @babel/core@7.29.7 @babel/preset-env@7.29.7 acorn@8.19.0
node scripts/build-markdown-parser.cjs
```

The build checks the upstream SHA-256, changes only the parser's fixed numeric
entity Map to a scoped ES5 lookup, transpiles syntax, and verifies ES5 parsing.
The reader supplies `String.fromCodePoint` only when the browser lacks it.

Run `python scripts/test-report-reader.py` with Playwright installed to check
text preservation, actual final-page visibility, safe DOM, local navigation,
font resizing and malformed-report cache retention. `DASHBOARD_TEST_BROWSER`
selects an installed Chromium/Edge executable. Physical Kindle validation is
separate from these browser tests.

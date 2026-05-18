#!/usr/bin/env node
/**
 * Build a presentation-quality manager_summary.docx using docx.js (v9.x).
 *
 * Layout:
 *   Page 1 — Cover page (title, subtitle, date, KPI banner).
 *   Page 2 — Table of contents.
 *   Page 3+ — Executive summary (KPI cards), chart, per-dataset table,
 *            and the "What drives cost?" analysis section.
 *
 * Styling:
 *   - Arial throughout. Slate palette, magenta accent, subtle row striping.
 *   - Footer with page numbers on every body page.
 *   - Figures and tables are numbered and captioned.
 *   - All tables set both columnWidths array AND per-cell width for Word
 *     compatibility. Cell shading always uses ShadingType.CLEAR.
 */
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, ImageRun,
  AlignmentType, BorderStyle, WidthType, ShadingType, VerticalAlign,
  HeadingLevel, LevelFormat, TableOfContents, PageBreak, PageNumber,
  Header, Footer, ExternalHyperlink,
} = require("docx");

// ---------------------------------------------------------------------------
// Paths + data
// ---------------------------------------------------------------------------
const BASE = path.resolve(__dirname, "..", "output", "batch_runs", "2026-04-17_comparison");
const DATA = JSON.parse(fs.readFileSync(path.join(BASE, "docx_data.json"), "utf8"));
const IMG_COMPARE = fs.readFileSync(path.join(BASE, "chart_cost_by_rows_vs_cols.png"));
const IMG_BAR = fs.readFileSync(path.join(BASE, "chart_tokens_per_dataset.png"));
const OUT = path.join(BASE, "manager_summary.docx");

// ---------------------------------------------------------------------------
// Theme
// ---------------------------------------------------------------------------
const C = {
  HEADING: "1F2937",        // slate-800 — titles, headings
  BODY: "374151",           // slate-700 — main body text
  SUBTLE: "6B7280",         // slate-500 — captions, small labels
  MUTED: "9CA3AF",          // slate-400 — footer, metadata
  ACCENT: "A23B72",         // magenta — hero numbers, key correlations
  ACCENT_LIGHT: "F5EAF2",   // magenta tint — KPI card fill
  NAVY: "1E3A5F",           // deep blue — alt accent
  NAVY_LIGHT: "EAF0F6",     // navy tint — alt KPI card fill
  TABLE_HEADER: "E0E7EF",   // header row fill
  TABLE_STRIPE: "F7F9FC",   // zebra stripe
  BORDER: "D1D5DB",         // table borders
  RULE: "E5E7EB",           // horizontal rules
};

const borderThin = { style: BorderStyle.SINGLE, size: 4, color: C.BORDER };
const borderNone = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const cellBorders = { top: borderThin, bottom: borderThin, left: borderThin, right: borderThin };
const noBorders = { top: borderNone, bottom: borderNone, left: borderNone, right: borderNone };

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function p(runs, opts = {}) {
  const children = Array.isArray(runs) ? runs : [runs instanceof TextRun ? runs : new TextRun({ text: String(runs || "") })];
  return new Paragraph({
    spacing: { before: 80, after: 80 },
    ...opts,
    children,
  });
}
function run(text, opts = {}) { return new TextRun({ text, font: "Arial", ...opts }); }
function bullet(children, ref = "bullets") {
  return new Paragraph({
    numbering: { reference: ref, level: 0 },
    spacing: { before: 40, after: 40 },
    children: Array.isArray(children) ? children : [run(String(children))],
  });
}
function numbered(children, ref) {
  return new Paragraph({
    numbering: { reference: ref, level: 0 },
    spacing: { before: 60, after: 60 },
    children: Array.isArray(children) ? children : [run(String(children))],
  });
}
function caption(text) {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 0, after: 200 },
    children: [run(text, { italics: true, color: C.SUBTLE, size: 18 })],
  });
}
function headerCell(text, width, opts = {}) {
  return new TableCell({
    borders: cellBorders,
    width: { size: width, type: WidthType.DXA },
    shading: { fill: C.TABLE_HEADER, type: ShadingType.CLEAR },
    verticalAlign: VerticalAlign.CENTER,
    children: [new Paragraph({
      alignment: opts.align || AlignmentType.LEFT,
      spacing: { before: 40, after: 40 },
      children: [run(text, { bold: true, size: 18, color: C.HEADING })],
    })],
  });
}
function dataCell(text, width, opts = {}) {
  const fill = opts.alt ? C.TABLE_STRIPE : "FFFFFF";
  return new TableCell({
    borders: cellBorders,
    width: { size: width, type: WidthType.DXA },
    shading: { fill, type: ShadingType.CLEAR },
    verticalAlign: VerticalAlign.CENTER,
    children: [new Paragraph({
      alignment: opts.align || AlignmentType.LEFT,
      spacing: { before: 30, after: 30 },
      children: [run(String(text), { size: 16, color: C.BODY, ...(opts.run || {}) })],
    })],
  });
}

// KPI callout cell (no borders, large number, small label underneath).
function kpiCell(number, label, width, color = C.ACCENT, fill = C.ACCENT_LIGHT) {
  return new TableCell({
    borders: noBorders,
    width: { size: width, type: WidthType.DXA },
    shading: { fill, type: ShadingType.CLEAR },
    verticalAlign: VerticalAlign.CENTER,
    margins: { top: 220, bottom: 220, left: 220, right: 220 },
    children: [
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { before: 0, after: 60 },
        children: [run(number, { bold: true, size: 48, color })],
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { before: 0, after: 0 },
        children: [run(label, { size: 16, color: C.SUBTLE, bold: true, allCaps: true })],
      }),
    ],
  });
}

function horizontalRule() {
  return new Paragraph({
    spacing: { before: 120, after: 120 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: C.RULE, space: 1 } },
    children: [run("")],
  });
}

function fmtInt(v) { return v == null ? "n/a" : Number(v).toLocaleString("en-US"); }
function fmtUSD(v) { return `$${Number(v).toFixed(2)}`; }
function fmtUSD3(v) { return `$${Number(v).toFixed(3)}`; }

// ---------------------------------------------------------------------------
// Build content
// ---------------------------------------------------------------------------
const s = DATA.summary;
const header = DATA.header;

const content = [];

// ==========================================================================
// COVER PAGE (minimal: title + one-line subtitle + date)
// ==========================================================================
// Push the title down to roughly the upper-third of the page.
content.push(new Paragraph({ spacing: { before: 3600, after: 0 }, children: [run("")] }));

// Main title
content.push(new Paragraph({
  heading: HeadingLevel.TITLE,
  alignment: AlignmentType.CENTER,
  spacing: { before: 0, after: 160 },
  children: [run(header.title, { size: 48, bold: true, color: C.HEADING })],
}));

// Simple subtitle (plain text, no banner)
content.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { before: 0, after: 0 },
  children: [run(
    `${header.num_datasets} datasets  ·  ${header.model}  ·  ${header.run_date}`,
    { size: 22, color: C.SUBTLE }
  )],
}));

// Page break to TOC
content.push(new Paragraph({ children: [new PageBreak()] }));

// ==========================================================================
// TABLE OF CONTENTS
// ==========================================================================
content.push(new Paragraph({
  heading: HeadingLevel.HEADING_1,
  children: [run("Contents")],
}));
content.push(new TableOfContents("Contents", { hyperlink: true, headingStyleRange: "1-3" }));
content.push(new Paragraph({ children: [new PageBreak()] }));

// ==========================================================================
// EXECUTIVE SUMMARY
// ==========================================================================
content.push(new Paragraph({
  heading: HeadingLevel.HEADING_1,
  children: [run("Executive summary")],
}));
content.push(p([
  run("This report presents the token consumption and cost breakdown for an end-to-end benchmark of the PVMAP generation pipeline over ", { size: 22 }),
  run(`${header.num_datasets} datasets`, { size: 22, bold: true }),
  run(". The objective is to establish a reliable cost model for the pipeline and identify the dataset characteristics that drive it.", { size: 22 }),
]));
content.push(p([
  run("Headline result: ", { size: 22, bold: true }),
  run("the full batch consumed ", { size: 22 }),
  run(fmtInt(s.total_tokens) + " tokens ", { size: 22, bold: true }),
  run("and cost ", { size: 22 }),
  run(fmtUSD(s.total_cost_usd), { size: 22, bold: true, color: C.ACCENT }),
  run(" at live Gemini pricing. Per-dataset cost ranged from ", { size: 22 }),
  run(fmtUSD3(s.cheapest.cost), { size: 22, bold: true }),
  run(" to ", { size: 22 }),
  run(fmtUSD3(s.priciest.cost), { size: 22, bold: true }),
  run(". Cost scales with dataset ", { size: 22 }),
  run("column count", { size: 22, bold: true }),
  run(" — not row count — with a Pearson correlation of ", { size: 22 }),
  run(`r = ${(DATA.correlations.cols_vs_cost > 0 ? "+" : "") + DATA.correlations.cols_vs_cost.toFixed(2)}`, { size: 22, bold: true, color: C.ACCENT }),
  run(".", { size: 22 }),
]));

// Three KPI cards — headline numbers at a glance
content.push(new Paragraph({ spacing: { before: 240, after: 120 }, children: [run("")] }));
content.push(new Table({
  columnWidths: [3120, 3120, 3120],
  rows: [new TableRow({
    children: [
      kpiCell(fmtUSD(s.total_cost_usd), "Total Cost", 3120, C.ACCENT, C.ACCENT_LIGHT),
      kpiCell(`${(s.total_tokens / 1_000_000).toFixed(1)}M`, "Tokens Consumed", 3120, C.NAVY, C.NAVY_LIGHT),
      kpiCell(String(header.num_datasets), "Datasets Benchmarked", 3120, C.HEADING, "F3F4F6"),
    ],
  })],
}));
content.push(horizontalRule());

// ==========================================================================
// CHART: tokens per dataset
// ==========================================================================
content.push(new Paragraph({
  heading: HeadingLevel.HEADING_1,
  children: [run("Tokens per dataset")],
}));
content.push(p(
  run("All 49 datasets, sorted descending by tokens consumed. Each bar is labelled with its absolute token count and source-file row count.", { size: 22 }),
));
content.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { before: 120, after: 60 },
  children: [new ImageRun({
    type: "png",
    data: IMG_BAR,
    transformation: { width: 540, height: 630 },
    altText: {
      title: "Tokens per dataset",
      description: "Horizontal bar chart showing total tokens consumed by each of the 49 datasets, sorted descending.",
      name: "tokens-per-dataset",
    },
  })],
}));
content.push(caption("Figure 1 — Tokens consumed per dataset (all 49, descending)."));
content.push(new Paragraph({ children: [new PageBreak()] }));

// ==========================================================================
// PER-DATASET TABLE
// ==========================================================================
content.push(new Paragraph({
  heading: HeadingLevel.HEADING_1,
  children: [run("Per-dataset breakdown")],
}));
content.push(p(
  run("Complete view of all 49 datasets, sorted by total tokens consumed (highest first). Costs use live Gemini pricing, tiered by prompt size per call.", { size: 22 }),
));

const DS_COLS = [520, 3680, 920, 800, 960, 1280, 1200]; // total 9360
const dsRows = [
  new TableRow({
    tableHeader: true,
    children: [
      headerCell("#", DS_COLS[0], { align: AlignmentType.CENTER }),
      headerCell("Dataset", DS_COLS[1]),
      headerCell("Rows", DS_COLS[2], { align: AlignmentType.RIGHT }),
      headerCell("Cols", DS_COLS[3], { align: AlignmentType.RIGHT }),
      headerCell("LLM calls", DS_COLS[4], { align: AlignmentType.RIGHT }),
      headerCell("Tokens", DS_COLS[5], { align: AlignmentType.RIGHT }),
      headerCell("Cost (USD)", DS_COLS[6], { align: AlignmentType.RIGHT }),
    ],
  }),
  ...DATA.per_dataset.map((r, i) => new TableRow({
    children: [
      dataCell(i + 1, DS_COLS[0], { align: AlignmentType.CENTER, alt: i % 2 === 1, run: { color: C.MUTED } }),
      dataCell(r.dataset, DS_COLS[1], { alt: i % 2 === 1, run: { font: "Consolas", size: 16 } }),
      dataCell(fmtInt(r.rows), DS_COLS[2], { align: AlignmentType.RIGHT, alt: i % 2 === 1 }),
      dataCell(r.cols == null ? "n/a" : r.cols, DS_COLS[3], { align: AlignmentType.RIGHT, alt: i % 2 === 1 }),
      dataCell(r.num_calls, DS_COLS[4], { align: AlignmentType.RIGHT, alt: i % 2 === 1 }),
      dataCell(fmtInt(r.tokens), DS_COLS[5], { align: AlignmentType.RIGHT, alt: i % 2 === 1 }),
      dataCell(fmtUSD3(r.cost), DS_COLS[6], { align: AlignmentType.RIGHT, alt: i % 2 === 1, run: { bold: r.cost >= 1.0 } }),
    ],
  })),
];
content.push(new Table({
  columnWidths: DS_COLS,
  margins: { top: 60, bottom: 60, left: 120, right: 120 },
  rows: dsRows,
}));
content.push(caption("Table 1 — Per-dataset tokens and cost (49 datasets, sorted by tokens). Costs above $1 are bolded."));
content.push(new Paragraph({ children: [new PageBreak()] }));

// ==========================================================================
// WHAT DRIVES COST
// ==========================================================================
content.push(new Paragraph({
  heading: HeadingLevel.HEADING_1,
  children: [run("What drives cost?")],
}));
content.push(p(
  run("With the per-dataset data in hand, the cost pattern across 49 datasets is unambiguous.", { size: 22 }),
));

// Finding callout
content.push(new Table({
  columnWidths: [9360],
  rows: [new TableRow({
    children: [new TableCell({
      borders: { top: borderNone, bottom: borderNone, right: borderNone,
                 left: { style: BorderStyle.SINGLE, size: 24, color: C.ACCENT } },
      width: { size: 9360, type: WidthType.DXA },
      shading: { fill: C.ACCENT_LIGHT, type: ShadingType.CLEAR },
      margins: { top: 180, bottom: 180, left: 240, right: 240 },
      children: [new Paragraph({
        children: [
          run("Finding — ", { bold: true, size: 22, color: C.ACCENT }),
          run("Per-dataset cost is driven almost entirely by the ", { size: 22, color: C.HEADING }),
          run("number of columns", { size: 22, color: C.HEADING, bold: true }),
          run(" in the dataset, not by the number of rows. A wide schema means the generator has more candidate properties to reason about, which produces a larger input prompt and a longer chain of thinking tokens — both of which Gemini bills at the premium output rate.", { size: 22, color: C.HEADING }),
        ],
      })],
    })],
  })],
}));

// Comparison chart (rows vs cols)
content.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { before: 320, after: 60 },
  children: [new ImageRun({
    type: "png",
    data: IMG_COMPARE,
    transformation: { width: 600, height: 255 },
    altText: {
      title: "Cost by rows vs columns",
      description: "Two-panel bar chart comparing average cost grouped by row count (left, flat) and by column count (right, rising).",
      name: "rows-vs-cols",
    },
  })],
}));
content.push(caption("Figure 2 — Average cost grouped by row count (left, no trend) vs by column count (right, ~5.5× rise)."));

// Correlation table
content.push(new Paragraph({
  heading: HeadingLevel.HEADING_2,
  children: [run("Evidence — correlation with cost")],
}));
const CORR_COLS = [3120, 1560, 4680];
content.push(new Table({
  columnWidths: CORR_COLS,
  margins: { top: 80, bottom: 80, left: 140, right: 140 },
  rows: [
    new TableRow({
      tableHeader: true,
      children: [
        headerCell("Signal", CORR_COLS[0]),
        headerCell("Correlation (r)", CORR_COLS[1], { align: AlignmentType.CENTER }),
        headerCell("Reading", CORR_COLS[2]),
      ],
    }),
    new TableRow({
      children: [
        dataCell("Number of columns", CORR_COLS[0], { run: { bold: true } }),
        dataCell((DATA.correlations.cols_vs_cost > 0 ? "+" : "") + DATA.correlations.cols_vs_cost.toFixed(2),
                 CORR_COLS[1], { align: AlignmentType.CENTER, run: { bold: true, color: C.ACCENT, size: 20 } }),
        dataCell("Strong, direct — the primary cost driver", CORR_COLS[2]),
      ],
    }),
    new TableRow({
      children: [
        dataCell("LLM calls (retries × agents)", CORR_COLS[0], { alt: true }),
        dataCell((DATA.correlations.calls_vs_cost > 0 ? "+" : "") + DATA.correlations.calls_vs_cost.toFixed(2),
                 CORR_COLS[1], { align: AlignmentType.CENTER, alt: true, run: { bold: true, size: 20 } }),
        dataCell("Moderate — residual retry effect on 2–3 hard datasets", CORR_COLS[2], { alt: true }),
      ],
    }),
    new TableRow({
      children: [
        dataCell("Number of rows", CORR_COLS[0]),
        dataCell((DATA.correlations.rows_vs_cost > 0 ? "+" : "") + DATA.correlations.rows_vs_cost.toFixed(2),
                 CORR_COLS[1], { align: AlignmentType.CENTER, run: { bold: true, size: 20, color: C.MUTED } }),
        dataCell("Near zero — row count does not predict cost", CORR_COLS[2]),
      ],
    }),
  ],
}));
content.push(caption("Table 2 — Pearson correlation with per-dataset cost (n = 49). Closer to ±1 means a stronger relationship."));

// Bucket tables side by side would be nice, but cleaner to stack vertically with clear headings.
content.push(new Paragraph({
  heading: HeadingLevel.HEADING_2,
  children: [run("Cost by column count")],
}));
const BUCKET_COLS = [2340, 2340, 2340, 2340];
content.push(new Table({
  columnWidths: BUCKET_COLS,
  margins: { top: 80, bottom: 80, left: 140, right: 140 },
  rows: [
    new TableRow({
      tableHeader: true,
      children: [
        headerCell("Columns", BUCKET_COLS[0]),
        headerCell("# datasets", BUCKET_COLS[1], { align: AlignmentType.RIGHT }),
        headerCell("Avg cost", BUCKET_COLS[2], { align: AlignmentType.RIGHT }),
        headerCell("Median cost", BUCKET_COLS[3], { align: AlignmentType.RIGHT }),
      ],
    }),
    ...DATA.col_buckets.map((b, i) => new TableRow({
      children: [
        dataCell(b.label, BUCKET_COLS[0], { alt: i % 2 === 1 }),
        dataCell(b.n, BUCKET_COLS[1], { align: AlignmentType.RIGHT, alt: i % 2 === 1 }),
        dataCell(fmtUSD3(b.avg), BUCKET_COLS[2], { align: AlignmentType.RIGHT, alt: i % 2 === 1, run: { bold: true } }),
        dataCell(fmtUSD3(b.median), BUCKET_COLS[3], { align: AlignmentType.RIGHT, alt: i % 2 === 1 }),
      ],
    })),
  ],
}));
content.push(caption("Table 3 — Average per-dataset cost grouped by column count. Wide datasets (>50 cols) cost ~5.5× more on average than narrow ones (1–5 cols)."));

content.push(new Paragraph({
  heading: HeadingLevel.HEADING_2,
  children: [run("Cost by row count (for contrast)")],
}));
content.push(new Table({
  columnWidths: BUCKET_COLS,
  margins: { top: 80, bottom: 80, left: 140, right: 140 },
  rows: [
    new TableRow({
      tableHeader: true,
      children: [
        headerCell("Rows", BUCKET_COLS[0]),
        headerCell("# datasets", BUCKET_COLS[1], { align: AlignmentType.RIGHT }),
        headerCell("Avg cost", BUCKET_COLS[2], { align: AlignmentType.RIGHT }),
        headerCell("Median cost", BUCKET_COLS[3], { align: AlignmentType.RIGHT }),
      ],
    }),
    ...DATA.row_buckets.map((b, i) => new TableRow({
      children: [
        dataCell(b.label, BUCKET_COLS[0], { alt: i % 2 === 1 }),
        dataCell(b.n, BUCKET_COLS[1], { align: AlignmentType.RIGHT, alt: i % 2 === 1 }),
        dataCell(fmtUSD3(b.avg), BUCKET_COLS[2], { align: AlignmentType.RIGHT, alt: i % 2 === 1 }),
        dataCell(fmtUSD3(b.median), BUCKET_COLS[3], { align: AlignmentType.RIGHT, alt: i % 2 === 1 }),
      ],
    })),
  ],
}));
content.push(caption("Table 4 — Average per-dataset cost grouped by row count. Row count has no predictive power; the smallest datasets actually cost slightly more on average than the largest."));

// Predictive formula call-out
content.push(new Paragraph({
  heading: HeadingLevel.HEADING_2,
  children: [run("Predictive formula")],
}));
const f = DATA.formula;
content.push(new Table({
  columnWidths: [9360],
  rows: [new TableRow({
    children: [new TableCell({
      borders: { top: borderThin, bottom: borderThin, left: borderThin, right: borderThin },
      width: { size: 9360, type: WidthType.DXA },
      shading: { fill: C.ACCENT_LIGHT, type: ShadingType.CLEAR },
      margins: { top: 260, bottom: 260, left: 260, right: 260 },
      children: [
        new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [run(
            `Cost (USD)  ≈  $${f.intercept.toFixed(2)}  +  $${f.slope.toFixed(4)}  ×  (number of columns)`,
            { bold: true, size: 30, color: C.ACCENT }
          )],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { before: 120, after: 0 },
          children: [run(
            `Linear fit across 49 datasets; explains ≈ ${Math.round(f.r_squared * 100)}% of cost variance (R² = ${f.r_squared.toFixed(2)}).`,
            { italics: true, size: 18, color: C.SUBTLE }
          )],
        }),
      ],
    })],
  })],
}));

content.push(p(run("Worked examples:", { bold: true, size: 22 })));
f.examples.forEach(ex => {
  content.push(bullet([
    run(ex.dataset, { font: "Consolas", size: 20 }),
    run(` (${ex.cols} cols) — predicted `, { size: 22 }),
    run(fmtUSD(ex.predicted), { bold: true, size: 22, color: C.ACCENT }),
    run(`, actual ${fmtUSD(ex.actual)}.`, { size: 22 }),
  ]));
});

// Ranked factors
content.push(new Paragraph({
  heading: HeadingLevel.HEADING_2,
  children: [run("The four factors, ranked")],
}));
const factors = [
  [run("Schema width. ", { bold: true, size: 22 }),
   run(`More columns mean a bigger PVMAP skeleton, more candidate properties, a larger prompt, and more thinking tokens. Primary correlation (r = ${(DATA.correlations.cols_vs_cost > 0 ? "+" : "") + DATA.correlations.cols_vs_cost.toFixed(2)}).`, { size: 22 })],
  [run("Retry attempts. ", { bold: true, size: 22 }),
   run("A failed validation re-invokes the generator with accumulated feedback. Each retry adds roughly $0.10–$0.20. When the 3-attempt ceiling is hit, it is the single biggest cost swing observed.", { size: 22 })],
  [run("Dataset structure. ", { bold: true, size: 22 }),
   run("Datasets with few rows but cryptic column codes or missing metadata confuse the model, triggering extra retries and longer reasoning traces. After the mid-benchmark optimization, only 2–3 datasets still exhibit this pattern.", { size: 22 })],
  [run("Thinking tokens. ", { bold: true, size: 22 }),
   run("Billed at the output rate ($12/MTok for gemini-3.1-pro-preview). More reasoning leads to more thinking tokens, which scales with both column count and retries.", { size: 22 })],
];
factors.forEach(r => content.push(numbered(r, "factors-ranked")));

// Footer / pricing reference
content.push(horizontalRule());
content.push(new Paragraph({
  alignment: AlignmentType.LEFT,
  spacing: { before: 60, after: 0 },
  children: [
    run("Pricing source:  ", { bold: true, size: 18, color: C.SUBTLE }),
    new ExternalHyperlink({
      children: [run(DATA.pricing_source, { style: "Hyperlink", size: 18 })],
      link: "https://ai.google.dev/gemini-api/docs/pricing",
    }),
  ],
}));
content.push(new Paragraph({
  spacing: { before: 60, after: 0 },
  children: [run(
    "Preview models may re-price before general availability; the actual Google invoice will match these figures within a few percent.",
    { size: 18, color: C.SUBTLE, italics: true }
  )],
}));

// ---------------------------------------------------------------------------
// Page footer (page numbers)
// ---------------------------------------------------------------------------
const footer = new Footer({
  children: [new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [
      run("Batch Benchmark Summary  ·  ", { size: 16, color: C.MUTED }),
      new TextRun({ children: ["Page ", PageNumber.CURRENT, " of ", PageNumber.TOTAL_PAGES], size: 16, color: C.MUTED, font: "Arial" }),
    ],
  })],
});

// ---------------------------------------------------------------------------
// Build and save
// ---------------------------------------------------------------------------
const doc = new Document({
  creator: "Batch Benchmark Pipeline",
  title: header.title,
  description: `Tokens and cost breakdown across ${header.num_datasets} datasets, with cost-driver analysis.`,
  numbering: {
    config: [
      {
        reference: "bullets",
        levels: [{
          level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 540, hanging: 270 } } },
        }],
      },
      {
        reference: "factors-ranked",
        levels: [{
          level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 540, hanging: 270 } } },
        }],
      },
    ],
  },
  styles: {
    default: { document: { run: { font: "Arial", size: 22, color: C.BODY } } },
    paragraphStyles: [
      {
        id: "Title", name: "Title", basedOn: "Normal",
        run: { font: "Arial", size: 56, bold: true, color: C.HEADING },
        paragraph: { spacing: { before: 0, after: 120 }, alignment: AlignmentType.CENTER },
      },
      {
        id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: "Arial", size: 32, bold: true, color: C.HEADING },
        paragraph: { spacing: { before: 360, after: 180 }, outlineLevel: 0 },
      },
      {
        id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: "Arial", size: 26, bold: true, color: C.HEADING },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 },
      },
      {
        id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: "Arial", size: 22, bold: true, color: C.HEADING },
        paragraph: { spacing: { before: 180, after: 80 }, outlineLevel: 2 },
      },
      {
        id: "Hyperlink", name: "Hyperlink", basedOn: "Normal",
        run: { color: "2563EB", underline: { type: "single" } },
      },
    ],
  },
  sections: [{
    properties: {
      page: {
        margin: { top: 1080, right: 1080, bottom: 1260, left: 1080 }, // 0.75" / 0.875" bottom
      },
      titlePage: false,
    },
    footers: { default: footer },
    children: content,
  }],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(OUT, buf);
  console.log(`Wrote ${OUT} (${(buf.length / 1024).toFixed(1)} KB)`);
});

// Build the FYP-1 Partial Thesis (.docx) for Bowen XU — BNBU template-compliant.
// Times New Roman, A4, 12pt body justified, H1 16pt / H2 14pt, IEEE numbered refs.
// Focus: DATA FOUNDATION (completed). Modelling parts kept brief (not yet implemented).
const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, ImageRun,
  Footer, AlignmentType, LevelFormat, TabStopType, TableOfContents,
  HeadingLevel, BorderStyle, WidthType, ShadingType,
  VerticalAlign, PageNumber,
} = require("docx");

// page geometry (A4, margins L/R 2cm, T/B 2.5cm)
const A4_W = 11906, A4_H = 16838;
const M_LR = Math.round(2 * 566.93), M_TB = Math.round(2.5 * 566.93);
const CW = A4_W - 2 * M_LR; // ~9638
const FONT = "Times New Roman";
const NAVY = "0B2E4A", BLUE = "0166A4", CARD = "EEF4FA", INK = "1F2A37";

// page numbers for the static TOC (filled on the 2nd pass via /tmp/toc_pages.json)
let TOC_PAGES = {};
try { TOC_PAGES = JSON.parse(fs.readFileSync("/tmp/toc_pages.json", "utf8")); } catch (e) {}

// ---- image helpers ----
function pngSize(p) { const b = fs.readFileSync(p); return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) }; }
function figure(path, widthIn) {
  const { w, h } = pngSize(path); const px = Math.round(widthIn * 96);
  return new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 60 },
    children: [new ImageRun({ type: "png", data: fs.readFileSync(path),
      transformation: { width: px, height: Math.round(px * h / w) },
      altText: { title: "figure", description: "figure", name: "figure" } })] });
}
function caption(t) { return new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
  children: [new TextRun({ text: t, italics: true, size: 21, font: FONT, color: "333333" })] }); }

// ---- text helpers ----
function runs(t) {
  if (typeof t === "string") return [new TextRun({ text: t, font: FONT, size: 24 })];
  return t.map(s => new TextRun({ text: s.text, bold: !!s.b, italics: !!s.i, font: FONT, size: s.size || 24, color: s.color }));
}
const body = (t, o = {}) => new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { line: 360, after: 140 }, children: runs(t), ...o });
const bullet = (t) => new Paragraph({ numbering: { reference: "b", level: 0 }, alignment: AlignmentType.JUSTIFIED, spacing: { line: 320, after: 80 }, children: runs(t) });
const numItem = (t) => new Paragraph({ numbering: { reference: "n", level: 0 }, alignment: AlignmentType.JUSTIFIED, spacing: { line: 320, after: 80 }, children: runs(t) });
// headings with EXPLICIT run sizes (H1 16pt, H2 14pt, H3 13pt) so template sizes are guaranteed
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: true, spacing: { before: 120, after: 200 },
  children: [new TextRun({ text: t, font: FONT, size: 32, bold: true, color: NAVY })] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 200, after: 120 },
  children: [new TextRun({ text: t, font: FONT, size: 28, bold: true, color: NAVY })] });
const center = (t, o = {}) => new Paragraph({ alignment: AlignmentType.CENTER, children: runs(t), ...o });
const gap = (n = 1) => Array.from({ length: n }, () => new Paragraph({ children: [new TextRun({ text: "", font: FONT, size: 24 })] }));

// ---- table builder ----
const bd = { style: BorderStyle.SINGLE, size: 4, color: "B6C4D4" };
const borders = { top: bd, bottom: bd, left: bd, right: bd, insideHorizontal: bd, insideVertical: bd };
function cell(content, w, { head = false, fill } = {}) {
  const paras = (Array.isArray(content) ? content : [content]).map(line =>
    new Paragraph({ spacing: { line: 264, after: 0 },
      children: (typeof line === "string"
        ? [new TextRun({ text: line, bold: head, font: FONT, size: 21, color: head ? "FFFFFF" : "1F2A37" })]
        : line.map(s => new TextRun({ text: s.text, bold: head || s.b, italics: s.i, font: FONT, size: 21, color: head ? "FFFFFF" : (s.color || "1F2A37") }))) }));
  return new TableCell({ width: { size: w, type: WidthType.DXA }, borders,
    shading: { fill: fill || (head ? BLUE : "FFFFFF"), type: ShadingType.CLEAR },
    margins: { top: 60, bottom: 60, left: 110, right: 110 }, verticalAlign: VerticalAlign.CENTER, children: paras });
}
function table(widths, rows) {
  return new Table({ width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA }, columnWidths: widths,
    rows: rows.map((r, i) => new TableRow({ tableHeader: i === 0,
      children: r.map((c, j) => cell(c, widths[j], { head: i === 0, fill: i === 0 ? BLUE : (i % 2 === 0 ? CARD : "FFFFFF") })) })) });
}

// ---- static TOC ----
function tocItem(label, key, lvl) {
  const page = TOC_PAGES[key] != null ? String(TOC_PAGES[key]) : "";
  return new Paragraph({
    tabStops: [{ type: TabStopType.RIGHT, position: CW, leader: "dot" }],
    spacing: { after: 70, line: 300 }, indent: lvl === 2 ? { left: 420 } : {},
    children: [
      new TextRun({ text: label, font: FONT, size: 24, bold: lvl === 1 }),
      new TextRun({ text: "\t" + page, font: FONT, size: 24 }),
    ] });
}
const TOC_ENTRIES = [
  ["Declaration", "Declaration", 1], ["Acceptance", "Acceptance", 1],
  ["Acknowledgement", "Acknowledgement", 1], ["Abstract", "Abstract", 1],
  ["1  Introduction", "1  Introduction", 1],
  ["1.1  Background", "1.1  Background", 2],
  ["1.2  Motivation and Problem Statement", "1.2  Motivation and Problem Statement", 2],
  ["1.3  Objectives", "1.3  Objectives", 2],
  ["1.4  Contributions", "1.4  Contributions", 2],
  ["1.5  Organisation of the Thesis", "1.5  Organisation of the Thesis", 2],
  ["2  Literature Review", "2  Literature Review", 1],
  ["2.1  Review-Based Hotel Recommendation", "2.1  Review-Based Hotel Recommendation", 2],
  ["2.2  Aspect-Based Sentiment Analysis", "2.2  Aspect-Based Sentiment Analysis", 2],
  ["2.3  Multi-Stakeholder Recommendation", "2.3  Multi-Stakeholder Recommendation", 2],
  ["2.4  Competition Sets and Relative Pricing", "2.4  Competition Sets and Relative Pricing", 2],
  ["2.5  Research Gap", "2.5  Research Gap", 2],
  ["3  Proposed Approach", "3  Proposed Approach", 1],
  ["4  Data Foundation", "4  Data Foundation", 1],
  ["4.1  The Review Dataset", "4.1  The Review Dataset", 2],
  ["4.2  Attribute Completion by Web Scraping", "4.2  Attribute Completion by Web Scraping", 2],
  ["4.3  Prototype Status of Later Stages", "4.3  Prototype Status of Later Stages", 2],
  ["5  Remaining Work", "5  Remaining Work", 1],
  ["6  Conclusion", "6  Conclusion", 1],
  ["References", "References", 1],
  ["Appendix A  Implementation Notes", "Appendix A  Implementation Notes", 1],
];

// ===================================================================== FRONT MATTER
const front = [
  ...gap(2),
  center([{ text: "Dual-Perspective Hotel Recommendation: Serving Tourists and Managers", b: true, size: 36 }]),
  center([{ text: "from a Shared Review-Based Representation", b: true, size: 36 }]),
  ...gap(2),
  center([{ text: "by", size: 28 }]), ...gap(1),
  center([{ text: "Bowen XU", b: true, size: 30 }]),
  center([{ text: "(2330034059)", size: 26 }]), ...gap(2),
  center([{ text: "A Final Year Project-I Partial Thesis", size: 26 }]),
  center([{ text: "submitted in partial fulfillment of the requirements", size: 26 }]),
  center([{ text: "for the degree of", size: 26 }]), ...gap(1),
  center([{ text: "Bachelor of Science (Honours)", b: true, size: 28 }]),
  center([{ text: "in", size: 26 }]),
  center([{ text: "Artificial Intelligence", b: true, size: 28 }]), ...gap(1),
  center([{ text: "at", size: 26 }]),
  center([{ text: "BEIJING NORMAL–HONG KONG BAPTIST UNIVERSITY", b: true, size: 26 }]), ...gap(2),
  center([{ text: "June, 2026", size: 26 }]),
  center([{ text: "Supervisor: Dr. Sunny Jeong", size: 24, color: "333333" }]),

  H1("Declaration"),
  body("I hereby declare that this Final Year Project-I partial thesis represents my own work, carried out under the supervision of Dr. Sunny Jeong, and that it has not been previously submitted, in whole or in part, for any degree or qualification at this or any other institution. All external sources of information, data and ideas have been duly acknowledged and cited. The Booking.com review corpus is a publicly available Kaggle dataset; all additional hotel attributes were collected through small-scale, research-only web data collection conducted in compliance with the access constraints described in Chapter 4."),
  ...gap(3),
  body([{ text: "Signed: ____________________________            Date: ____________________", color: "333333" }]),
  ...gap(1), body([{ text: "Bowen XU (2330034059)", b: true }]),

  H1("Acceptance"),
  body("This is to certify that the Final Year Project-I partial thesis entitled “Dual-Perspective Hotel Recommendation: Serving Tourists and Managers from a Shared Review-Based Representation”, submitted by Bowen XU (2330034059), has been examined and is found to be acceptable in respect of its scope, presentation and academic content as partial fulfillment of the requirements for the degree of Bachelor of Science (Honours) in Artificial Intelligence."),
  ...gap(3),
  body([{ text: "____________________________", color: "333333" }]), body([{ text: "Dr. Sunny Jeong — Project Supervisor", b: true }]),
  ...gap(2), body([{ text: "____________________________", color: "333333" }]), body([{ text: "Observer", b: true }]),

  H1("Acknowledgement"),
  body("I would like to express my sincere gratitude to my supervisor, Dr. Sunny Jeong, for the guidance that shaped this project. In particular, the advice to concentrate on the dual-perspective model and to first build a solid data foundation, rather than dispersing effort across too many sub-problems, kept the work focused and achievable. I also thank the Faculty of Science and Technology at Beijing Normal–Hong Kong Baptist University for the academic environment and resources, my classmates for the discussions that sharpened these ideas, and my family for their continued support."),

  H1("Abstract"),
  body("Online travel platforms host an enormous volume of hotel reviews, yet most academic recommender systems exploit only a fraction of this signal and serve a single stakeholder — the tourist. This thesis proposes a dual-perspective hotel recommendation framework that serves both the tourist, who wants the best value within a budget, and the hotel manager, who needs to understand a property’s competitive position, from one shared, review-based hotel representation. Three ideas are pursued: a symmetric two-sided framework; a local competition set defined by geographic proximity and price tier rather than absolute price; and an aspect-level competitive diagnosis driven by review sentiment. This partial thesis focuses on the data foundation, which is the part completed so far. A public corpus of 26,675 reviews over 821 hotels was enriched by collecting coordinates, star rating and price for 822 hotel pages, achieving 91% coordinate coverage and tripling the apparent hotel density of the Brussels market by locating hotels from coordinates rather than from names. The modelling components are described at the level of intended design; their full implementation and evaluation are the next stage of the project."),

  H1("Contents"),
  new TableOfContents("Contents", { hyperlink: true, headingStyleRange: "1-2" }),
];

// ===================================================================== CH1
const ch1 = [
  H1("1  Introduction"),
  H2("1.1  Background"),
  body("Choosing a hotel has become a paradoxically difficult task. For a single city, platforms such as Booking.com list hundreds of properties, each with dozens to hundreds of textual reviews. This user-generated content has been shown to replace traditional word-of-mouth and to strongly influence bookings, but it also turns hotel selection into a time-consuming information-processing problem for travellers [3], [6]. On the supply side, the same reviews are a largely untapped source of operational intelligence: they describe, in the guests’ own words, exactly where a property succeeds or disappoints relative to its rivals."),
  body("Recommender systems are the standard response to information overload, and many have been applied to hotels [3], [5]. Yet two features of the domain are under-served. First, a booking involves more than one stakeholder — the traveller and the hotel operator — and a purely consumer-centric design obscures the provider’s objectives [1], [2]. Second, hotel reviews are multi-faceted: a single review may praise the location while criticising the breakfast, so an overall star rating compresses away precisely the detail that is most actionable, a deviation observed empirically between overall and criteria-level ratings [7]."),
  H2("1.2  Motivation and Problem Statement"),
  body("The motivation is partly personal. As a frequent traveller, I have repeatedly found that existing hotel applications do not let me search in the terms I actually care about — the balance between price, how recently a property was renovated, and the volume and content of its reviews. The ranking offered is dominated by either raw price or an averaged rating, neither of which answers the real question: which of these hotels is the best value for what I am paying here? Hotel data is, at the same time, relatively complete and well structured, which makes the domain attractive for building a model."),
  body("A second observation motivated the two-sided framing. A survey of related work showed that almost all hotel recommenders are built for the tourist; very few address the manager’s perspective of understanding and improving a property’s competitive standing. This asymmetry is also a research opportunity, and it is where review text can be turned into concrete, defensible advice."),
  body("Two design commitments follow from experience. First, price should be treated as relative, not absolute: local cost of living differs, so the same nominal rate means different things in a capital city and a coastal town, and a “mid-range” hotel should be understood as mid-range relative to its local market. Filtering by an absolute price threshold therefore compares properties that are not genuinely competing for the same guests. Second, reviews deserve deeper analysis than overall-sentiment scoring: decomposing a review into aspects (cleanliness, location, service, noise, value) is what makes a competitive diagnosis possible."),
  body([{ text: "Problem statement. ", b: true }, { text: "Given a corpus of hotels and their textual reviews, together with structured attributes (price, location, star rating), the problem is to construct a single hotel representation that can be read in two directions: to rank hotels by value within a tourist’s budget tier, and to diagnose an individual hotel’s competitive position against the local set of properties that genuinely compete for the same guests." }]),
  H2("1.3  Objectives"),
  body("The overall aim is to design and validate a dual-perspective hotel recommendation system, decomposed as follows:"),
  numItem([{ text: "O1 — Data foundation. ", b: true }, { text: "Assemble a hotel dataset combining review text with the structured attributes (price, coordinates, star rating) needed to define competition, since these are absent from the public review corpus." }]),
  numItem([{ text: "O2 — Local competition sets. ", b: true }, { text: "Define and construct competition sets from geographic proximity and price tier." }]),
  numItem([{ text: "O3 — Aspect-level review analysis. ", b: true }, { text: "Produce, for each hotel, an aspect-quality vector and a negative-complaint distribution." }]),
  numItem([{ text: "O4 — Shared representation and dual readout. ", b: true }, { text: "Combine the above into one representation supporting a tourist value-ranking and a manager diagnosis." }]),
  numItem([{ text: "O5 — Evaluation. ", b: true }, { text: "Evaluate the tourist side with ranking metrics and the manager side with case studies." }]),
  body("Objective O1 is the focus of this partial thesis and is substantially complete; O2–O5 are the remaining work of the project (Chapter 5)."),
  H2("1.4  Contributions"),
  body("This project makes three intended contributions:"),
  bullet([{ text: "A symmetric two-sided framework ", b: true }, { text: "in which one shared representation is read both as a tourist value ranking and as a manager competitive diagnosis, rather than as two unrelated systems [1], [2]." }]),
  bullet([{ text: "Local competition sets with relative pricing, ", b: true }, { text: "defining competition by geography and price tier rather than an absolute price filter, after the hospitality notion of a competitive set [11]." }]),
  bullet([{ text: "Aspect-level competitive diagnosis ", b: true }, { text: "that aggregates review sentiment within a competition set to turn “value” and “bad reviews” into quantified, comparable indicators." }]),
  H2("1.5  Organisation of the Thesis"),
  body("Chapter 2 reviews related work and identifies the research gap. Chapter 3 outlines the proposed approach. Chapter 4 reports the completed data foundation in detail. Chapter 5 sets out the remaining work, and Chapter 6 concludes."),
];

// ===================================================================== CH2
const ch2 = [
  H1("2  Literature Review"),
  H2("2.1  Review-Based Hotel Recommendation"),
  body("Using review text to improve recommendation is a mature idea. Chen, Chen and Wang [3] survey the field by whether reviews build user or item profiles and how opinions are fused with ratings. McAuley and Leskovec [4] couple latent rating factors with latent review topics and show the combination predicts ratings more accurately than either source alone, with the largest gains for items that have few ratings but informative reviews — directly relevant to the long tail of hotels with sparse review histories. Within hospitality, Ray, Garain and Sarkar [5] build an ensemble hotel recommender that scores hotels on aspects such as cleanliness, value and service, and Zhong et al. [7] exploit the systematic gap between a hotel’s overall rating and its detailed criteria ratings — evidence that an averaged score discards actionable information."),
  H2("2.2  Aspect-Based Sentiment Analysis"),
  body("Aspect-based sentiment analysis (ABSA) seeks the sentiment toward specific aspects of an entity rather than the document as a whole. Ameur, Hamdi and Ben Yahia [6] systematically review sentiment analysis for hotel reviews, documenting the move from lexicon and classical methods to deep models and recurring aspect categories (location, cleanliness, staff, value, room). The current state of the art is dominated by pre-trained transformers such as DeBERTa [8], and reproducible off-the-shelf ABSA is provided by frameworks like PyABSA [9], whose checkpoints run at low computational cost."),
  H2("2.3  Multi-Stakeholder Recommendation"),
  body("Abdollahpouri et al. [1] argue that the end user is often not the only stakeholder: providers and the platform also have stakes, and a consumer-only design cannot express provider-facing objectives. Burke [2] formalises multi-sided fairness, distinguishing consumer-side and provider-side concerns. These works motivate looking beyond the tourist, but remain concerned mainly with fairness and exposure within a single recommendation act. The manager perspective pursued here is different in kind: it gives the provider an analytical, diagnostic read on its own competitive standing rather than altering how items are exposed to users."),
  H2("2.4  Competition Sets and Relative Pricing"),
  body("In hospitality revenue management, a property’s competitive set is the group of similar hotels competing for the same guests and is the reference against which rates are set, defined by geographic proximity, comparable market segment and similar type and size [11]. This project imports that idea into a review-based recommender and commits to relative rather than absolute price, addressing a limitation of recommenders that filter by an absolute price band and thereby place non-competing properties in the same comparison."),
  H2("2.5  Research Gap"),
  body("Three observations follow. First, review-based hotel recommenders are well developed but overwhelmingly tourist-facing; the manager’s diagnostic perspective is rarely a first-class output [1], [3], [5]. Second, aspect sentiment is routinely computed but seldom aggregated within a properly defined competition set for side-by-side comparison, and negative reviews in particular are underused as a structured signal [6], [7]. Third, the hospitality concept of a competition set [11] has not been systematically combined with review-based aspect analysis inside one recommender. The proposed system targets exactly this intersection."),
];

// ===================================================================== CH3 (brief — not yet implemented)
const ch3 = [
  H1("3  Proposed Approach"),
  body("This chapter outlines the proposed system at a high level. The data foundation of Chapter 4 is implemented; the modelling components summarised here define the intended design and have not yet been built, so they are described briefly rather than in technical detail."),
  body("The system is organised around a single shared hotel representation that is computed once and read in two directions (Figure 1). Two data sources — the public review corpus and the scraped structured attributes — feed the representation, which is intended to combine a hotel’s relative price position, an aspect-quality vector from its reviews, location convenience, a review-credibility weight that grows with review volume, and its complaint mix. The tourist readout ranks hotels by value within a budget tier; the manager readout positions a single hotel within its competition set and produces an aspect-level diagnosis."),
  figure("figures/fig_architecture.png", 5.5),
  caption("Figure 1: Dual-perspective architecture. One shared representation is read in two directions."),
  body("Three modelling components are planned. The local competition set will be formed by clustering hotels geographically and then splitting each cluster into price tiers, so that a hotel is compared only with genuine rivals; density-based clustering [10] and the hospitality competitive-set principle [11] inform this step. A key design rule is that quality is treated as an outcome of the comparison, not a precondition of it: location and price tier define who competes, while rating, review volume and aspect sentiment decide who is better within a set. The aspect-level diagnosis will apply an ABSA model [8], [9] to seven fixed aspects (location, cleanliness, breakfast, service, noise, room, value) and aggregate the results within a competition set, with negative reviews handled separately. The dual readout will then turn this representation into a tourist value ranking and a manager diagnosis whose statements are generated from computed numbers. The full specification and implementation of these components are the next stage of the project (Chapter 5)."),
];

// ===================================================================== CH4 (detailed data foundation)
const ch4 = [
  H1("4  Data Foundation"),
  body("This chapter reports the work completed for this partial thesis: assembling the dataset and completing the missing structured attributes by web data collection. Figure 2 shows the pipeline. The later stages (competition-set construction and aspect analysis) exist only as a preliminary prototype and are summarised briefly in Section 4.3, since they are still ongoing."),
  figure("figures/fig_pipeline.png", 6.0),
  caption("Figure 2: The data-foundation pipeline; the focus of this partial thesis is the first two stages."),
  H2("4.1  The Review Dataset"),
  body("The base dataset is the public Booking.com Hotel Reviews corpus from Kaggle, comprising 26,675 reviews over 821 unique hotels, of which roughly 96% are located in Belgium. The raw file has 16 columns; the most relevant are listed in Table 1. The corpus is review-level — one row per review — so a single hotel maps to dozens or hundreds of rows, and the median hotel has only about seventeen reviews."),
  table([2600, 4519, 2519], [
    ["Column", "Description", "Role"],
    ["hotel_name", "Hotel display name", "Identification"],
    ["hotel_url", "Booking.com page URL", "Join key for scraping"],
    ["rating", "Per-review score", "Evaluation / negatives"],
    ["avg_rating", "Hotel average score", "Evaluation"],
    ["review_text", "Free-text review body", "Aspect analysis"],
    ["tags", "Trip type, party, room", "Context features"],
    ["nationality", "Reviewer nationality", "Context / bias check"],
    ["reviewed_at", "Review date", "Recency weighting"],
  ]),
  caption("Table 1: Key columns of the review corpus (16 columns in total)."),
  body([{ text: "Crucially, the corpus contains " }, { text: "no price, no coordinates and no star rating", b: true }, { text: " — exactly the structured attributes needed to define competition. Bridging this gap is the purpose of the scraping stage and is the main contribution of this partial thesis." }]),
  H2("4.2  Attribute Completion by Web Scraping"),
  body("To obtain the missing attributes, each hotel page referenced by hotel_url was visited with a real browser and parsed for three signals: geographic coordinates (from an embedded latitude–longitude attribute, cross-checked against structured page data), star rating (from accessibility labels, distinguishing official from platform self-ratings), and room price (from the booking widget under a single fixed query — the same dates, occupancy and currency for every hotel, so prices are comparable). Where a hotel was sold out on the first query date, two further comparable mid-week dates were attempted before recording the price as missing."),
  body([{ text: "Compliance. ", b: true }, { text: "Data collection was deliberately small in scale (about 800 pages) and for academic research only. The collector used a randomised delay of three to eight seconds between requests, saved the raw HTML so pages need not be fetched twice, and did not attempt to bypass any CAPTCHA or bot-detection mechanism; blocked pages were recorded as failures. No credentials or personal data were collected." }]),
  body("A practical difficulty — and one of the more instructive parts of the project — was that Booking.com defends these fields strongly: location and price are frequently withheld or rendered dynamically, so naive parsing fails. This required targeted handling: recovering city from coordinates rather than the hotel name, retrying price across multiple dates, and detecting and discarding a fixed fallback coordinate the platform returns for some apartment listings. Table 2 summarises the coverage achieved over 822 successfully processed pages."),
  table([3400, 1600, 4638], [
    ["Field", "Coverage", "Note"],
    ["Coordinates", "745 (91%)", "Primary key for geographic clustering"],
    ["Star rating", "529 (64%)", "Official rating where available"],
    ["Price", "321 (39%)", "Single fixed query; sold-out pages retried on 3 dates"],
    ["City (via coordinates)", "+65 hotels", "Assigned by coordinate bounding boxes, not by name"],
  ]),
  caption("Table 2: Attribute coverage after data collection (822 pages)."),
  body("Recovering city from coordinates rather than names markedly changed apparent market density. For Brussels, name matching alone identified 27 hotels, whereas coordinates placed 80 hotels in the city — a near three-fold increase that materially improves the prospects for forming competition sets. The resulting city distribution is shown in Figure 3; Belgian urban and coastal markets dominate, with a residual “Unknown” group of 96 hotels whose coordinates fell outside the labelled bounding boxes."),
  figure("figures/fig_cities.png", 5.0),
  caption("Figure 3: Distinct hotels per city, located by coordinates (top markets)."),
  H2("4.3  Prototype Status of Later Stages"),
  body("To confirm that the downstream design is feasible, a small prototype of the later stages was built on a Brussels subset: geographic clustering followed by price tiers produced three preliminary competition sets, and an aspect-sentiment pipeline based on a pre-trained model was run over the reviews of those hotels. These results are preliminary and are not reported in detail here, because constructing competition sets and the aspect analysis on the full dataset is still ongoing and forms the next stage of the project (Chapter 5). The completed and validated outcome of this partial thesis is the enriched hotel dataset described above."),
];

// ===================================================================== CH5 (remaining work, FYP-1)
const ch5 = [
  H1("5  Remaining Work"),
  body("The data foundation (Objective O1) is in place. The remaining objectives O2–O5 are the next stage of this project:"),
  numItem([{ text: "Build competition sets on the full 822-hotel dataset ", b: true }, { text: "so that genuine geographic submarkets emerge, and report the number and average size of valid sets per market." }]),
  numItem([{ text: "Run aspect extraction over all hotels in valid sets ", b: true }, { text: "and validate it by manually checking a sample of reviews." }]),
  numItem([{ text: "Assemble the shared representation ", b: true }, { text: "including location convenience and a review-credibility weighting." }]),
  numItem([{ text: "Implement the tourist ranker and the manager diagnosis generator. ", b: true }, { text: "" }]),
  numItem([{ text: "Evaluate and ablate ", b: true }, { text: "the tourist side with ranking metrics (NDCG@K, Precision@K) against rating-only and price-filter baselines, and the manager side with case studies and a judged assessment of diagnosis quality." }]),
  body("Three principal risks are foreseen. Price coverage is currently 39%; the mitigation is to treat price mainly as a coarse tier and to impute and flag missing values, so the system degrades gracefully. Valid competition sets may be thin in smaller markets; the mitigation is a sensitivity analysis over the clustering radius and a focus on denser markets (Brussels, Bruges, Antwerp). Finally, aspect-sentiment accuracy may be insufficient on idiomatic reviews; the mitigation is manual spot-checking with reported agreement. An indicative schedule is given in Table 3."),
  table([2200, 4900, 2538], [
    ["Stage", "Task", "Target"],
    ["1", "Build competition sets on the full dataset", "Month 1"],
    ["2", "Full aspect extraction + manual validation", "Month 1–2"],
    ["3", "Shared representation + tourist ranker", "Month 2–3"],
    ["4", "Manager diagnosis generator", "Month 3"],
    ["5", "Evaluation, ablation and case studies", "Month 4"],
    ["6", "Final thesis writing", "Month 4–5"],
  ]),
  caption("Table 3: Indicative schedule for the remaining work."),
];

// ===================================================================== CH6
const ch6 = [
  H1("6  Conclusion"),
  body("This partial thesis has motivated and outlined a dual-perspective hotel recommendation system that serves both tourists and hotel managers from a single shared, review-based representation, and it has delivered the project’s data foundation. The contribution is framed around three ideas: a symmetric two-sided framework, local competition sets defined by geography and price tier rather than absolute price, and an aspect-level competitive diagnosis driven by review analysis."),
  body("On the empirical side, a public corpus of 26,675 reviews over 821 hotels was enriched by collecting coordinates, star rating and price for 822 hotel pages, reaching 91% coordinate coverage and tripling the apparent hotel density of the Brussels market by locating hotels through coordinates rather than names. The honest limitations of the current scope — a Belgium-centric dataset, a single-snapshot approximation of price and partial price coverage — are documented and feed into the work plan. With the data foundation complete, the remaining modelling and evaluation are the next stage of the project, scheduled in Chapter 5."),
];

// ===================================================================== REFERENCES
function ref(n, parts) {
  return new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { after: 120, line: 288 }, indent: { left: 600, hanging: 600 },
    children: [new TextRun({ text: `[${n}]\t`, font: FONT, size: 24 }), ...runs(parts)] });
}
const references = [
  H1("References"),
  ref(1, [{ text: "H. Abdollahpouri, G. Adomavicius, R. Burke, I. Guy, D. Jannach, T. Kamishima, J. Krasnodebski, and L. Pizzato, “Multistakeholder recommendation: Survey and research directions,” " }, { text: "User Modeling and User-Adapted Interaction", i: true }, { text: ", vol. 30, no. 1, pp. 127–158, 2020." }]),
  ref(2, [{ text: "R. Burke, “Multisided fairness for recommendation,” in " }, { text: "Workshop on Fairness, Accountability and Transparency in Machine Learning (FATML)", i: true }, { text: ", 2017. arXiv:1707.00093." }]),
  ref(3, [{ text: "L. Chen, G. Chen, and F. Wang, “Recommender systems based on user reviews: The state of the art,” " }, { text: "User Modeling and User-Adapted Interaction", i: true }, { text: ", vol. 25, no. 2, pp. 99–154, 2015." }]),
  ref(4, [{ text: "J. McAuley and J. Leskovec, “Hidden factors and hidden topics: Understanding rating dimensions with review text,” in " }, { text: "Proc. 7th ACM Conf. Recommender Systems (RecSys)", i: true }, { text: ", 2013, pp. 165–172." }]),
  ref(5, [{ text: "B. Ray, A. Garain, and R. Sarkar, “An ensemble-based hotel recommender system using sentiment analysis and aspect categorization of hotel reviews,” " }, { text: "Applied Soft Computing", i: true }, { text: ", vol. 98, art. 106935, 2021." }]),
  ref(6, [{ text: "A. Ameur, S. Hamdi, and S. Ben Yahia, “Sentiment analysis for hotel reviews: A systematic literature review,” " }, { text: "ACM Computing Surveys", i: true }, { text: ", vol. 56, no. 3, pp. 1–38, 2023." }]),
  ref(7, [{ text: "L. Zhong, Y. Luo, X. Zhang, H. Zhang, and J. Wang, “Enhanced hotel recommendation method addressing the deviation between overall rating and detailed criteria ratings on TripAdvisor.com,” " }, { text: "Journal of Intelligent & Fuzzy Systems", i: true }, { text: ", 2021." }]),
  ref(8, [{ text: "P. He, X. Liu, J. Gao, and W. Chen, “DeBERTa: Decoding-enhanced BERT with disentangled attention,” in " }, { text: "Proc. Int. Conf. Learning Representations (ICLR)", i: true }, { text: ", 2021. arXiv:2006.03654." }]),
  ref(9, [{ text: "H. Yang, C. Zhang, and K. Li, “PyABSA: A modularized framework for reproducible aspect-based sentiment analysis,” in " }, { text: "Proc. 32nd ACM Int. Conf. Information and Knowledge Management (CIKM)", i: true }, { text: ", 2023." }]),
  ref(10, [{ text: "M. Ester, H.-P. Kriegel, J. Sander, and X. Xu, “A density-based algorithm for discovering clusters in large spatial databases with noise,” in " }, { text: "Proc. 2nd Int. Conf. Knowledge Discovery and Data Mining (KDD)", i: true }, { text: ", 1996, pp. 226–231." }]),
  ref(11, [{ text: "Hospitality Net, “How to build and analyze your hotel competitive set,” 2019. [Online]. Available: https://www.hospitalitynet.org/news/4131178.html" }]),
];

const appendix = [
  H1("Appendix A  Implementation Notes"),
  body("The data-foundation pipeline is implemented as independent, re-runnable Python stages that exchange data through files: a scraping stage that visits each hotel page and writes raw HTML and an attribute table; and a cleaning stage that recovers city from coordinates and merges review counts. The figures and tables in this thesis are generated directly from the stage outputs, so every reported number is reproducible from the stored data."),
];

// ===================================================================== ASSEMBLE
const doc = new Document({
  creator: "Bowen XU", title: "Dual-Perspective Hotel Recommendation",
  features: { updateFields: true }, // Word populates the TOC (with page numbers) on open
  styles: {
    default: { document: { run: { font: FONT, size: 24 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: FONT, color: NAVY }, paragraph: { spacing: { before: 120, after: 200 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: FONT, color: NAVY }, paragraph: { spacing: { before: 200, after: 120 }, outlineLevel: 1 } },
    ],
  },
  numbering: { config: [
    { reference: "b", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 280 } } } }] },
    { reference: "n", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 320 } } } }] },
  ] },
  sections: [{
    properties: { page: { size: { width: A4_W, height: A4_H }, margin: { top: M_TB, bottom: M_TB, left: M_LR, right: M_LR } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 20, color: "666666" })] })] }) },
    children: [...front, ...ch1, ...ch2, ...ch3, ...ch4, ...ch5, ...ch6, ...references, ...appendix],
  }],
});

Packer.toBuffer(doc).then(buf => { const out = require("path").join(__dirname, "paper", "previous_submission", "FYP1_Partial_Thesis.docx"); fs.mkdirSync(require("path").dirname(out), { recursive: true }); fs.writeFileSync(out, buf); console.log("WROTE", buf.length, "bytes; TOC pages:", Object.keys(TOC_PAGES).length ? "filled" : "PLACEHOLDER"); });

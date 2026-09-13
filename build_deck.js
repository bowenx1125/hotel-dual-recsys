const pptxgen = require("pptxgenjs");
const p = new pptxgen();
p.defineLayout({ name: "W", width: 13.333, height: 7.5 });
p.layout = "W";
p.author = "FYP";
p.title = "From Kaggle to a Scraped Hotel Database";

// ---- palette (BNBU brand: blue + gold) ----
const NAVY = "0B2E4A", BLUE = "0166A4", BLUELT = "8FC1E3";
const GOLD = "C0892B", GOLDLT = "E6C57E";
const INK = "1F2A37", MUTE = "6B7785", CARD = "EEF4FA", WHITE = "FFFFFF", LINE = "D8E2EC";
const F = "Calibri";
const shadow = () => ({ type: "outer", color: "0B2E4A", blur: 9, offset: 3, angle: 90, opacity: 0.13 });

function eyebrow(s, txt, x, y, color) {
  s.addText(txt, { x, y, w: 11, h: 0.35, fontFace: F, fontSize: 13, bold: true, color: color || GOLD, charSpacing: 3 });
}
// big section number + title header for content slides
function header(s, num, title) {
  s.addText(num, { x: 0.6, y: 0.45, w: 1.6, h: 1.2, fontFace: F, fontSize: 60, bold: true, color: GOLDLT, align: "left", valign: "middle" });
  s.addText(title, { x: 1.95, y: 0.5, w: 10.7, h: 1.1, fontFace: F, fontSize: 30, bold: true, color: NAVY, valign: "middle" });
}
function statCard(s, x, y, w, h, big, label, bigColor) {
  s.addShape(p.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: CARD }, line: { color: LINE, width: 1 }, rectRadius: 0.1, shadow: shadow() });
  s.addText(big, { x, y: y + 0.18, w, h: h * 0.55, fontFace: F, fontSize: 46, bold: true, color: bigColor || BLUE, align: "center", valign: "middle" });
  s.addText(label, { x, y: y + h * 0.62, w, h: h * 0.32, fontFace: F, fontSize: 15, color: MUTE, align: "center", valign: "top" });
}
function dotRow(s, x, y, w, color, label, text) {
  s.addShape(p.shapes.OVAL, { x, y: y + 0.06, w: 0.26, h: 0.26, fill: { color } });
  s.addText([
    { text: label + "  ", options: { bold: true, color: INK } },
    { text: text, options: { color: MUTE } },
  ], { x: x + 0.42, y, w: w - 0.42, h: 0.5, fontFace: F, fontSize: 17, valign: "middle" });
}

// ============================ SLIDE 1 — TITLE ============================
let s = p.addSlide();
s.background = { color: NAVY };
// subtle corner accent: a large faint gold oval bottom-right
s.addShape(p.shapes.OVAL, { x: 10.6, y: 5.3, w: 5.2, h: 5.2, fill: { color: BLUE, transparency: 78 } });
s.addShape(p.shapes.OVAL, { x: 12.0, y: 6.4, w: 3.0, h: 3.0, fill: { color: GOLD, transparency: 82 } });
eyebrow(s, "FINAL YEAR PROJECT   ·   DATA FOUNDATION", 0.85, 1.55, GOLDLT);
s.addText("From Kaggle to a\nScraped Hotel Database", { x: 0.85, y: 2.05, w: 11.4, h: 2.2, fontFace: F, fontSize: 46, bold: true, color: WHITE, lineSpacingMultiple: 1.02 });
s.addText("Building the data layer for a dual-perspective hotel recommender", { x: 0.9, y: 4.35, w: 10.5, h: 0.6, fontFace: F, fontSize: 19, color: BLUELT });
// bottom stat strip
s.addShape(p.shapes.LINE, { x: 0.9, y: 5.55, w: 6.2, h: 0, line: { color: GOLDLT, width: 1.5 } });
s.addText([
  { text: "26,675", options: { bold: true, color: WHITE } }, { text: " reviews      ", options: { color: BLUELT } },
  { text: "821", options: { bold: true, color: WHITE } }, { text: " hotels      ", options: { color: BLUELT } },
  { text: "822", options: { bold: true, color: WHITE } }, { text: " scraped", options: { color: BLUELT } },
], { x: 0.9, y: 5.75, w: 11, h: 0.5, fontFace: F, fontSize: 18 });
s.addText("FYP Progress Report   ·   June 2026", { x: 0.9, y: 6.75, w: 8, h: 0.4, fontFace: F, fontSize: 13, color: MUTE });

// ============================ SLIDE 2 — PART 1 DATASET ============================
s = p.addSlide(); s.background = { color: WHITE };
header(s, "01", "The Kaggle Dataset");
statCard(s, 0.6, 1.95, 3.85, 1.95, "26,675", "reviews");
statCard(s, 4.74, 1.95, 3.85, 1.95, "821", "unique hotels");
statCard(s, 8.88, 1.95, 3.85, 1.95, "96%", "in Belgium", GOLD);
s.addText("Why this dataset", { x: 0.6, y: 4.35, w: 12, h: 0.5, fontFace: F, fontSize: 19, bold: true, color: NAVY });
dotRow(s, 0.6, 5.0, 12.1, BLUE, "Fits the goal:", "has review text + hotel_url, enough for a dual-perspective study");
dotRow(s, 0.6, 5.65, 12.1, GOLD, "But incomplete:", "no price, no coordinates, no star rating");
s.addShape(p.shapes.ROUNDED_RECTANGLE, { x: 0.6, y: 6.45, w: 12.13, h: 0.7, fill: { color: NAVY }, rectRadius: 0.08 });
s.addText("These three missing fields are exactly what the recommender needs  —  so they must be scraped.", { x: 0.8, y: 6.45, w: 11.8, h: 0.7, fontFace: F, fontSize: 15, italic: true, color: WHITE, valign: "middle" });

// ============================ SLIDE 3 — PART 2 STRUCTURE ============================
s = p.addSlide(); s.background = { color: WHITE };
header(s, "02", "What the Data Looks Like");
// left: one-hotel -> many-reviews diagram
s.addText("One row = one review", { x: 0.6, y: 1.95, w: 6, h: 0.4, fontFace: F, fontSize: 17, bold: true, color: NAVY });
s.addShape(p.shapes.ROUNDED_RECTANGLE, { x: 0.6, y: 2.95, w: 2.4, h: 1.0, fill: { color: BLUE }, rectRadius: 0.08, shadow: shadow() });
s.addText("1 hotel\n(hotel_url)", { x: 0.6, y: 2.95, w: 2.4, h: 1.0, fontFace: F, fontSize: 15, bold: true, color: WHITE, align: "center", valign: "middle" });
// vertical spine + horizontal stubs (all positive geometry)
s.addShape(p.shapes.LINE, { x: 3.35, y: 2.85, w: 0, h: 1.4, line: { color: BLUELT, width: 1.75 } });
const ry = [2.55, 3.25, 3.95];
ry.forEach((yy, i) => {
  s.addShape(p.shapes.LINE, { x: 3.35, y: yy + 0.3, w: 0.65, h: 0, line: { color: BLUELT, width: 1.75 } });
  s.addShape(p.shapes.ROUNDED_RECTANGLE, { x: 4.0, y: yy, w: 2.6, h: 0.6, fill: { color: CARD }, line: { color: LINE, width: 1 }, rectRadius: 0.06 });
  s.addText("review " + (i + 1), { x: 4.0, y: yy, w: 2.6, h: 0.6, fontFace: F, fontSize: 13, color: MUTE, align: "center", valign: "middle" });
});
s.addText("dozens to hundreds per hotel", { x: 4.0, y: 4.7, w: 2.7, h: 0.4, fontFace: F, fontSize: 12, italic: true, color: MUTE, align: "center" });
// right: key columns card
s.addShape(p.shapes.ROUNDED_RECTANGLE, { x: 7.1, y: 1.95, w: 5.63, h: 2.9, fill: { color: CARD }, line: { color: LINE, width: 1 }, rectRadius: 0.1, shadow: shadow() });
s.addText("16 columns  ·  key ones", { x: 7.4, y: 2.15, w: 5, h: 0.45, fontFace: F, fontSize: 17, bold: true, color: NAVY });
s.addText([
  { text: "hotel_name", options: { breakLine: false } }, { text: "   hotel_url", options: { breakLine: false } }, { text: "   rating\n", options: { breakLine: true } },
  { text: "review_text", options: { breakLine: false } }, { text: "   tags", options: { breakLine: false } }, { text: "   nationality", options: { breakLine: true } },
], { x: 7.4, y: 2.75, w: 5.1, h: 1.9, fontFace: "Consolas", fontSize: 16, color: BLUE, bold: true, lineSpacingMultiple: 1.6 });
// gap banner
s.addShape(p.shapes.ROUNDED_RECTANGLE, { x: 0.6, y: 5.55, w: 12.13, h: 1.3, fill: { color: "FBF3E3" }, line: { color: GOLDLT, width: 1 }, rectRadius: 0.1 });
s.addText("THE GAP", { x: 0.95, y: 5.75, w: 3, h: 0.4, fontFace: F, fontSize: 14, bold: true, color: GOLD, charSpacing: 2 });
s.addText("No price · no latitude/longitude · no star rating  →  competition sets cannot be built yet.", { x: 0.95, y: 6.15, w: 11.4, h: 0.6, fontFace: F, fontSize: 18, bold: true, color: NAVY });

// ============================ SLIDE 4 — PART 3 SCRAPING ============================
s = p.addSlide(); s.background = { color: WHITE };
header(s, "03", "Scraping the Missing Fields");
const steps = [
  ["1", "Visit", "A real Playwright browser opens each Booking.com page (passes the WAF check)"],
  ["2", "Extract", "Coordinates, stars & address from data-atlas-latlng + JSON-LD + aria-label"],
  ["3", "Price", "Try 3 candidate weekdays under one fixed query; retry if sold out"],
];
const sx = [0.6, 4.74, 8.88], sw = 3.85;
steps.forEach((st, i) => {
  const x = sx[i];
  s.addShape(p.shapes.ROUNDED_RECTANGLE, { x, y: 2.05, w: sw, h: 3.0, fill: { color: WHITE }, line: { color: LINE, width: 1.25 }, rectRadius: 0.1, shadow: shadow() });
  s.addShape(p.shapes.OVAL, { x: x + sw / 2 - 0.45, y: 2.35, w: 0.9, h: 0.9, fill: { color: BLUE } });
  s.addText(st[0], { x: x + sw / 2 - 0.45, y: 2.35, w: 0.9, h: 0.9, fontFace: F, fontSize: 30, bold: true, color: WHITE, align: "center", valign: "middle" });
  s.addText(st[1], { x, y: 3.4, w: sw, h: 0.5, fontFace: F, fontSize: 21, bold: true, color: NAVY, align: "center" });
  s.addText(st[2], { x: x + 0.3, y: 3.95, w: sw - 0.6, h: 1.0, fontFace: F, fontSize: 15, color: MUTE, align: "center", valign: "top" });
  if (i < 2) s.addText("→", { x: x + sw - 0.05, y: 2.05, w: 0.4, h: 3.0, fontFace: F, fontSize: 28, bold: true, color: GOLDLT, align: "center", valign: "middle" });
});
s.addShape(p.shapes.ROUNDED_RECTANGLE, { x: 0.6, y: 5.45, w: 12.13, h: 1.35, fill: { color: NAVY }, rectRadius: 0.1 });
s.addText("Research-compliant", { x: 0.95, y: 5.6, w: 5, h: 0.4, fontFace: F, fontSize: 14, bold: true, color: GOLDLT, charSpacing: 1 });
s.addText("Raw HTML saved for re-parsing   ·   3–8 s random delay   ·   no CAPTCHA or bot-check bypass", { x: 0.95, y: 6.0, w: 11.5, h: 0.6, fontFace: F, fontSize: 17, color: WHITE });

// ============================ SLIDE 5 — PART 4 RESULTS ============================
s = p.addSlide(); s.background = { color: WHITE };
header(s, "04", "What I Obtained");
statCard(s, 0.6, 1.9, 3.85, 1.55, "91%", "have coordinates");
statCard(s, 4.74, 1.9, 3.85, 1.55, "64%", "have star rating");
statCard(s, 8.88, 1.9, 3.85, 1.55, "39%", "have price", GOLD);
// city distribution — hand-drawn bars (no native chart, fully controlled)
s.addText("Hotels per city (by coordinates)", { x: 0.6, y: 3.75, w: 7, h: 0.4, fontFace: F, fontSize: 16, bold: true, color: NAVY });
const cities = [["Brussels", 80], ["Bruges", 62], ["Antwerp", 38], ["Ghent", 29], ["Ostend", 25]];
const baseY = 6.75, maxH = 1.95, bw = 0.92, slot = 1.4, x0 = 0.85;
s.addShape(p.shapes.LINE, { x: x0 - 0.15, y: baseY, w: 7.1, h: 0, line: { color: LINE, width: 1 } });
cities.forEach(([name, v], i) => {
  const h = v / 80 * maxH, x = x0 + i * slot, y = baseY - h;
  s.addShape(p.shapes.ROUNDED_RECTANGLE, { x, y, w: bw, h, fill: { color: i === 0 ? BLUE : "4E9AC4" }, rectRadius: 0.03 });
  s.addText(String(v), { x: x - 0.2, y: y - 0.42, w: bw + 0.4, h: 0.38, fontFace: F, fontSize: 16, bold: true, color: NAVY, align: "center" });
  s.addText(name, { x: x - 0.24, y: baseY + 0.06, w: bw + 0.48, h: 0.35, fontFace: F, fontSize: 12, color: MUTE, align: "center" });
});
// payoff callout
s.addShape(p.shapes.ROUNDED_RECTANGLE, { x: 8.3, y: 4.15, w: 4.43, h: 2.9, fill: { color: CARD }, line: { color: LINE, width: 1 }, rectRadius: 0.1, shadow: shadow() });
s.addText("Density payoff", { x: 8.6, y: 4.4, w: 3.9, h: 0.5, fontFace: F, fontSize: 17, bold: true, color: NAVY });
s.addText([
  { text: "27", options: { fontSize: 30, bold: true, color: MUTE } },
  { text: "  →  ", options: { fontSize: 24, color: GOLD } },
  { text: "80", options: { fontSize: 46, bold: true, color: BLUE } },
], { x: 8.6, y: 4.95, w: 3.9, h: 1.0, fontFace: F, valign: "middle" });
s.addText("Brussels hotels — name-matching found 27, coordinates revealed 80", { x: 8.6, y: 6.0, w: 3.85, h: 1.0, fontFace: F, fontSize: 14, color: MUTE, valign: "top" });

// ============================ SLIDE 6 — FUTURE WORK ============================
s = p.addSlide(); s.background = { color: WHITE };
eyebrow(s, "WHAT'S NEXT", 0.6, 0.55, GOLD);
s.addText("Future Work", { x: 0.6, y: 0.9, w: 11, h: 0.9, fontFace: F, fontSize: 32, bold: true, color: NAVY });
const fw = [
  "Improve data collection and validation — some hotel records may contain invalid or missing information.",
  "Extract detailed features from reviews (cleanliness, location, service, noise, value, facilities), not just ratings.",
  "Make the system query-driven, so users can ask specific questions, e.g. is the WiFi good, or is it close to public transport.",
  "Develop manager-side diagnosis: compare a hotel with nearby competitors and give improvement suggestions.",
  "Expand data sources from Booking to TripAdvisor, Google Reviews, and Agoda.",
  "Add fake-review detection — mark suspicious reviews that could distort sentiment and recommendations.",
  "Add a feedback mechanism: users rate whether recommendations are useful, to improve the system over time.",
];
function fwItem(idx, x, y, w) {
  s.addShape(p.shapes.OVAL, { x, y, w: 0.5, h: 0.5, fill: { color: NAVY } });
  s.addText(String(idx + 1), { x, y, w: 0.5, h: 0.5, fontFace: F, fontSize: 16, bold: true, color: GOLDLT, align: "center", valign: "middle" });
  s.addText(fw[idx], { x: x + 0.68, y: y - 0.06, w: w - 0.68, h: 1.05, fontFace: F, fontSize: 13.5, color: INK, valign: "top", lineSpacingMultiple: 1.0 });
}
const colW = 5.95, cx1 = 0.6, cx2 = 6.95, top = 2.05, gap = 1.16;
[0, 1, 2, 3].forEach((k, r) => fwItem(k, cx1, top + r * gap, colW));
[4, 5, 6].forEach((k, r) => fwItem(k, cx2, top + r * gap, colW));

// ============================ SLIDE 7 — CLOSING ============================
s = p.addSlide(); s.background = { color: NAVY };
s.addShape(p.shapes.OVAL, { x: -1.5, y: -1.5, w: 4.5, h: 4.5, fill: { color: BLUE, transparency: 80 } });
s.addShape(p.shapes.OVAL, { x: 11.2, y: 4.8, w: 4.0, h: 4.0, fill: { color: GOLD, transparency: 84 } });
s.addText("Thank You", { x: 0.9, y: 2.5, w: 11, h: 1.2, fontFace: F, fontSize: 54, bold: true, color: WHITE });
s.addShape(p.shapes.LINE, { x: 1.0, y: 3.85, w: 3.4, h: 0, line: { color: GOLDLT, width: 1.5 } });
s.addText("Next  →  build local competition sets from coordinates + price, then aspect-level review analysis", { x: 0.95, y: 4.1, w: 10.8, h: 0.8, fontFace: F, fontSize: 19, color: BLUELT });

const exportDir = require("path").join(__dirname, "paper", "previous_submission");
require("fs").mkdirSync(exportDir, { recursive: true });
p.writeFile({ fileName: require("path").join(exportDir, "FYP_Data_Foundation.pptx") }).then(f => console.log("WROTE", f));

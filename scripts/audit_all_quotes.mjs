#!/usr/bin/env node
/**
 * Full heuristic audit of data/characters.json (no GPT).
 * For GPT validation after deploy: POST /api/sanitize_appearance_quotes {"use_gpt":true}
 * or POST /api/reselect_appearance_quotes {"book_id":"...","use_gpt":true}
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const CHARACTERS_FILE = path.join(__dirname, '..', 'data', 'characters.json');

const SUSPECT = /\b(blood|bloody|Her face was|I remember her|my blood was|champing|mad with terror|bloodless lips)\b/i;

const PORTRAIT_ACTION = [
  /\b(blood|bloody|gore|smeared|smear|trickl\w*|stream of blood)\b/i,
  /\b(my|your|his|her)\s+blood\s+(was|were|had|ran|run)\b/i,
  /\b(champing|rage|fury|terror|scream|shriek|mad with)\b/i,
];
const SCENE_BEATS = [
  /\bred light of triumph in his eyes\b/i,
];

function shouldRemoveQuote(quote, name, aliases) {
  if (!quote || quote.length < 20) return false;
  const q = quote.trim();
  if (/^(her|his)\s+(face|lips|cheeks|throat)/i.test(q)) return true;
  if (/^the\s+(fair\s+)?(woman|man|lady|girl|boy)\b/i.test(q)) return true;
  if (SCENE_BEATS.some((p) => p.test(q))) return true;
  if (PORTRAIT_ACTION.some((p) => p.test(q))) return true;
  if (/\bI\s+remember\s+her\b/i.test(q)) return true;
  return false;
}

const chars = JSON.parse(fs.readFileSync(CHARACTERS_FILE, 'utf8'));
const byBook = new Map();
let zero = 0;
let bad = 0;
let suspect = 0;

for (const rec of chars) {
  const bookId = rec.book_id || 'unknown';
  if (!byBook.has(bookId)) byBook.set(bookId, { total: 0, zero: 0, bad: 0, suspect: 0, names: [] });
  const b = byBook.get(bookId);
  b.total++;
  const name = rec.character_name || '';
  const apq = rec.appearance_quotes || [];
  if (!apq.length) {
    zero++;
    b.zero++;
    if (b.names.length < 5) b.names.push(`${name} (no quotes)`);
    continue;
  }
  for (const q of apq) {
    const txt = (q.quote || '').trim();
    if (shouldRemoveQuote(txt, name, rec.aliases)) {
      bad++;
      b.bad++;
      if (b.names.length < 8) b.names.push(`${name}: BAD`);
      break;
    }
    if (SUSPECT.test(txt)) {
      suspect++;
      b.suspect++;
      if (b.names.length < 8) b.names.push(`${name}: suspect`);
      break;
    }
  }
}

console.log(`Total characters: ${chars.length}`);
console.log(`No appearance quotes: ${zero}`);
console.log(`Fails heuristic (should remove): ${bad}`);
console.log(`Suspect keywords: ${suspect}`);
console.log('\nBy book (worst first):');
const sorted = [...byBook.entries()].sort((a, b) => (b[1].bad + b[1].suspect + b[1].zero) - (a[1].bad + a[1].suspect + a[1].zero));
for (const [bookId, s] of sorted.slice(0, 25)) {
  if (s.bad + s.suspect + s.zero === 0) continue;
  console.log(`  ${bookId}: ${s.total} chars, zero=${s.zero}, bad=${s.bad}, suspect=${s.suspect}`);
  for (const n of s.names) console.log(`    - ${n}`);
}

console.log('\nNext steps after deploy:');
console.log('  GET  /api/audit_appearance_quotes');
console.log('  POST /api/sanitize_appearance_quotes  {"use_gpt":true}');
console.log('  POST /api/reselect_appearance_quotes  {"book_id":"gutenberg-345","use_gpt":true,"overwrite":...}');

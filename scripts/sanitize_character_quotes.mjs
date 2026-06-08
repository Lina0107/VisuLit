#!/usr/bin/env node
/**
 * Remove portrait-unsafe appearance_quotes from data/characters.json.
 * Keeps quotes unless they clearly describe someone else, gore, or horror action.
 *
 *   node scripts/sanitize_character_quotes.mjs
 *   node scripts/sanitize_character_quotes.mjs --write
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(__dirname, '..');
const CHARACTERS_FILE = path.join(ROOT, 'data', 'characters.json');
const write = process.argv.includes('--write');

const PORTRAIT_ACTION = [
  /\b(blood|bloody|gore|smeared|smear|trickl\w*|stream of blood)\b/i,
  /\b(champing|rage|fury|terror|scream|shriek|mad with)\b/i,
  /\b(grasped|grasp|seized|struck|attacked|bit(?:ing)?|throttle)\b/i,
];
const SCENE_BEATS = [
  /\bred light of triumph in his eyes\b/i,
  /\bkissing his hand to me\b/i,
];

function genderHint(name, aliases) {
  const blob = [name, ...(aliases || [])].join(' ');
  const hasF = /\b(miss|mrs|ms|madam|lady|queen|princess|duchess|countess|girl|woman)\b/i.test(blob);
  const hasM = /\b(mr|lord|sir|count|king|prince|duke|baron|dr|doctor)\b/i.test(blob);
  if (hasF && !hasM) return 'f';
  if (hasM && !hasF) return 'm';
  return null;
}

function mentionsCharacter(quote, name, aliases) {
  const seen = new Set();
  for (const raw of [name, ...(aliases || [])]) {
    const n = String(raw || '').trim();
    if (!n) continue;
    const key = n.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    const esc = n.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    if (n.length >= 6 || n.includes(' ')) {
      if (new RegExp(`\\b${esc}\\b`, 'i').test(quote)) return true;
    } else if (n.length >= 4) {
      if (new RegExp(`\\bthe\\s+${esc}\\b`, 'i').test(quote)) return true;
    }
  }
  return false;
}

function shouldRemoveQuote(quote, name, aliases) {
  if (!quote || quote.length < 20) return false;
  const q = quote.trim();
  const mentions = mentionsCharacter(q, name, aliases);

  if (/\bI\s+remember\s+(her|him)\b/i.test(q)) return true;
  if (/^(she|he)\s+(was|had|looked|appeared|seemed)\s+/i.test(q)) return true;
  if (/^(her|his)\s+(face|lips|cheeks|throat|neck|hair|eyes|countenance|chin|brow|forehead)\b/i.test(q) && !mentions) {
    return true;
  }
  if (/^the\s+(fair\s+)?(woman|man|lady|girl|boy)\b/i.test(q) && !mentions) return true;
  if (/\bby her side stood\b/i.test(q) && !mentions) return true;
  if (/\b(slender neck of the fair woman|fair woman and with)\b/i.test(q)) return true;

  const gh = genderHint(name, aliases);
  if (gh === 'm' && /^her\s+/i.test(q) && !mentions) return true;
  if (gh === 'f' && /^his\s+/i.test(q) && !mentions) return true;

  if (SCENE_BEATS.some((p) => p.test(q))) return true;
  if (PORTRAIT_ACTION.some((p) => p.test(q)) && !mentions) return true;

  return false;
}

const chars = JSON.parse(fs.readFileSync(CHARACTERS_FILE, 'utf8'));
let changed = 0;
let removed = 0;
const examples = [];

for (const rec of chars) {
  const name = rec.character_name || '';
  const aliases = rec.aliases || [];
  const before = rec.appearance_quotes || [];
  const after = [];
  for (const q of before) {
    const txt = (q.quote || '').trim();
    if (!txt) continue;
    if (shouldRemoveQuote(txt, name, aliases)) {
      removed++;
      if (examples.length < 30) examples.push(`${name}: ${txt.slice(0, 100)}…`);
    } else {
      after.push(q);
    }
  }
  if (after.length !== before.length) {
    changed++;
    if (write) rec.appearance_quotes = after;
  }
}

console.log(`Characters cleaned: ${changed}`);
console.log(`Quotes removed: ${removed}`);
if (examples.length) {
  console.log('\nRemoved examples:');
  for (const e of examples) console.log(`  - ${e}`);
}

const dracula = chars.find((c) => c.character_name === 'Count Dracula');
if (dracula) {
  const qs = write ? dracula.appearance_quotes : (dracula.appearance_quotes || []).filter(
    (q) => !shouldRemoveQuote((q.quote || '').trim(), dracula.character_name, dracula.aliases),
  );
  console.log(`\nCount Dracula quotes after clean: ${qs.length}`);
  for (const q of qs) console.log(`  • ${q.quote.slice(0, 130)}…`);
}

if (write) {
  fs.writeFileSync(CHARACTERS_FILE, JSON.stringify(chars, null, 2) + '\n', 'utf8');
  console.log(`\nWrote ${CHARACTERS_FILE}`);
} else {
  console.log('\nDry run. Use --write to save.');
}

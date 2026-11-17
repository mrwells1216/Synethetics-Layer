// Port of synesthetic/library.py: the grammar layer from our own word library, with no language
// model. Says which words are nouns, verbs, adjectives and adverbs. tools/parity.py checks this
// file against the Python one, so change them together.
import { PHRASES, PINS, WORD_CLASSES } from './library-data'

export type Kind = 'noun' | 'verb' | 'adjective' | 'adverb'
export type Tagged = { start: number; end: number; kind: Kind }

// Word classes. Small words: D the/your, E some/each, A these/both, P of/in, T to, S I/you,
// G me/them, H he/she/it, W that/which, L let's/you'll, K please, O not, X other. Helping verbs:
// M can/does, B is/has. Open words: V Vs Vd Vg verb forms, VN NV noun-or-verb (first letter = the
// usual side) and their -s forms VNs NVs, JV adjective-or-verb, J adjective, R adverb, Q adverb a
// verb follows, N noun, U not in the library.
const PIN_CLASS: Record<string, string> = { noun: 'N', verb: 'V', adjective: 'J', adverb: 'R', skip: 'X' }
const CLOSED = new Set('DEAPTSGHWLKOXMB'.split(''))
const THROUGH = new Set('ROQK'.split('')) // looked past when asking what came before
const NOUN_BEFORE = new Set('DPJEA'.split(''))
const VERB_BEFORE = new Set('TMLS'.split(''))
const LEX_VERB = new Set(['V', 'Vs', 'Vd', 'Vg'])
const OBJECT = new Set('DEAHG'.split(''))
const PARTICLES = new Set(['for', 'at', 'on', 'up', 'out', 'off', 'by', 'into', 'through', 'down', 'over', 'in'])
const ADJ_ENDS = ['ous', 'ful', 'less', 'able', 'ible', 'ive', 'ic', 'al', 'ary']
const NOUN_ENDS = ['tion', 'sion', 'ness', 'ity', 'ism', 'ship', 'ence', 'ance']
const MID = new Set(',>)]/&-–—%+=|~#@*_'.split(''))
const OPENERS = new Set(' \t\n"\'“”‘’(['.split(''))
const TOKEN_SRC = "[A-Za-z]+(?:['’][A-Za-z]+)?"

type Tok = {
  s: number
  e: number
  cls: string
  low: string
  poss: boolean
  pin: string | null
  hit: number
  lower: boolean
  start: boolean
}
type Hit = [number, number, string]

let table: Map<string, string> | null = null

function words(): Map<string, string> {
  if (table === null) {
    table = new Map()
    for (const cls of Object.keys(WORD_CLASSES)) {
      for (const w of WORD_CLASSES[cls].split(' ')) if (w) table.set(w, cls)
    }
  }
  return table
}

/** ASCII-only lowercase with straight apostrophes: the same length in every language. */
function lower(s: string): string {
  return s.replace(/[A-Z]/g, c => c.toLowerCase()).replace(/’/g, "'")
}

function wordish(c: string): boolean {
  return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9')
}

function phraseHits(low: string): Hit[] {
  const hits: Hit[] = []
  for (const [phrase, kind] of PHRASES) {
    let at = low.indexOf(phrase)
    while (at !== -1) {
      const end = at + phrase.length
      if (
        !(at > 0 && wordish(low[at - 1])) &&
        !(end < low.length && wordish(low[end])) &&
        hits.every(h => end <= h[0] || at >= h[1])
      ) {
        hits.push([at, end, kind])
      }
      at = low.indexOf(phrase, at + 1)
    }
  }
  hits.sort((a, b) => a[0] - b[0] || a[1] - b[1])
  return hits
}

function guess(w: string): string {
  const n = w.length
  if (n > 4 && w.endsWith('ly')) return 'R'
  if (n > 5 && (w.endsWith('ize') || w.endsWith('ify'))) return 'V'
  if (n > 6 && (w.endsWith('izes') || w.endsWith('ifies'))) return 'Vs'
  if (n > 5 && w.endsWith('ing')) return 'Vg'
  if (n > 4 && w.endsWith('ed') && !w.endsWith('eed')) return 'Vd'
  for (const end of ADJ_ENDS) {
    if (n > end.length + (end.length === 2 ? 2 : 1) && w.endsWith(end)) return 'J'
  }
  for (const end of NOUN_ENDS) {
    if (n > end.length + 2 && w.endsWith(end)) return 'N'
  }
  return 'U'
}

function midSentence(text: string, at: number): boolean {
  let j = at - 1
  while (j >= 0 && OPENERS.has(text[j])) j -= 1
  return j >= 0 && (wordish(text[j]) || MID.has(text[j]))
}

function blank(text: string, a: number, b: number): boolean {
  for (let i = a; i < b; i++) {
    const c = text[i]
    if (c !== ' ' && c !== '\t' && c !== '\n') return false
  }
  return true
}

function tagNow(text: string): Tagged[] {
  const lib = words()
  const lowText = lower(text)
  const hits = PHRASES.length ? phraseHits(lowText) : []
  const toks: Tok[] = []
  let hi = 0
  const re = new RegExp(TOKEN_SRC, 'g')
  let m: RegExpExecArray | null
  while ((m = re.exec(text)) !== null) {
    const s = m.index
    const e = s + m[0].length
    const low = lowText.slice(s, e)
    let stem = low
    let poss = false
    let cls: string | undefined = lib.get(low)
    if (cls === undefined && low.includes("'")) {
      if (low.endsWith("'s")) {
        stem = low.slice(0, -2)
        poss = true
        cls = lib.get(stem)
      } else {
        cls = low.endsWith("n't") ? 'M' : 'X'
      }
    }
    while (hi < hits.length && hits[hi][1] <= s) hi += 1
    const hit = hi < hits.length && hits[hi][0] <= s && e <= hits[hi][1] ? hi : -1
    const pin: string | null = hit >= 0 ? hits[hit][2] : Object.prototype.hasOwnProperty.call(PINS, stem) ? PINS[stem] : null
    const first = text[s]
    if (pin !== null) {
      cls = PIN_CLASS[pin]
    } else {
      if (cls === undefined) cls = guess(stem)
      if (!CLOSED.has(cls)) {
        const letters = text.slice(s, s + stem.length)
        if (
          (letters.length >= 2 && letters === letters.toUpperCase()) ||
          (first >= 'A' && first <= 'Z' && midSentence(text, s))
        ) {
          cls = 'N'
        }
      }
    }
    toks.push({ s, e, cls, low: stem, poss, pin, hit, lower: first >= 'a' && first <= 'z', start: !midSentence(text, s) })
  }

  const before = (at: number): [string, boolean] => {
    let i = at
    let crossed = false
    while (i > 0 && blank(text, toks[i - 1].e, toks[i].s)) {
      i -= 1
      const t = toks[i]
      if (t.poss) return ['D', crossed]
      if (THROUGH.has(t.cls)) {
        crossed = crossed || t.cls === 'Q' || t.cls === 'K'
        continue
      }
      return [t.cls, crossed]
    }
    return ['', crossed]
  }

  const after = (i: number): Tok | null =>
    i + 1 < toks.length && blank(text, toks[i].e, toks[i + 1].s) ? toks[i + 1] : null

  const kindOf = (i: number): Kind | null => {
    const t = toks[i]
    const c = t.cls
    if (t.pin !== null) return t.pin === 'skip' ? null : (t.pin as Kind)
    if (CLOSED.has(c)) return c === 'M' || c === 'B' ? 'verb' : null
    if (c === 'R' || c === 'Q') return 'adverb'
    if (c === 'J') return 'adjective'
    if (c === 'N') return 'noun'
    const [p, crossed] = before(i)
    const nxt = after(i)
    const n = nxt ? nxt.cls : ''
    const nOpen = nxt !== null && !CLOSED.has(n) && n !== 'R' && n !== 'Q'
    if (c === 'U') {
      if (
        t.lower &&
        (p === 'M' || p === 'L' || p === 'S' || ((p === 'H' || p === 'W') && t.low.length > 3 && t.low.endsWith('s')))
      ) {
        return 'verb'
      }
      return 'noun'
    }
    if (c === 'V') return p === 'D' ? 'noun' : 'verb'
    if (c === 'Vs') return 'verb'
    if (c === 'Vd') {
      if ((p === 'D' || p === 'P' || p === 'E' || p === 'A') && nOpen) return 'adjective'
      return p === 'D' ? 'noun' : 'verb'
    }
    if (c === 'Vg') {
      if (p === 'D') return nOpen ? 'adjective' : 'noun'
      return 'verb'
    }
    const verbLead = VERB_BEFORE.has(p) || (crossed && !NOUN_BEFORE.has(p))
    if (c === 'JV') {
      if (verbLead || OBJECT.has(n) || n === 'W') return 'verb'
      // "open Settings": an instruction when a capitalized name follows
      return n === 'N' && nxt !== null && !nxt.lower ? 'verb' : 'adjective'
    }
    if (c === 'NV' || c === 'VN') {
      if (verbLead || (c === 'VN' && p === 'A')) return 'verb'
      if (NOUN_BEFORE.has(p) || (c === 'NV' && LEX_VERB.has(p))) return 'noun'
      if (OBJECT.has(n) || n === 'W') return 'verb'
      if (n === 'M' || n === 'B') return 'noun'
      if (t.start && nxt !== null && PARTICLES.has(nxt.low)) return 'verb'
      return c === 'VN' ? 'verb' : 'noun'
    }
    // NVs / VNs: "lists", "shows"
    if (NOUN_BEFORE.has(p) || LEX_VERB.has(p)) return 'noun'
    if (p === 'H' || p === 'W' || OBJECT.has(n)) return 'verb'
    if (n === 'M' || n === 'B') return 'noun'
    return c === 'VNs' ? 'verb' : 'noun'
  }

  const out: Tagged[] = []
  let lastHit = -1
  for (let i = 0; i < toks.length; i++) {
    const t = toks[i]
    const kind = kindOf(i)
    if (kind === null) continue
    const joined = t.hit >= 0 && t.hit === lastHit // one pinned phrase, even across a hyphen
    lastHit = t.hit
    const prev = out[out.length - 1]
    if (prev && prev.kind === kind && (joined || blank(text, prev.end, t.s))) prev.end = t.e
    else out.push({ start: t.s, end: t.e, kind })
  }
  return out
}

const cache = new Map<string, Tagged[]>()

/** Each noun, verb, adjective and adverb in `text`; neighbours of one kind are joined. */
export function tag(text: string): Tagged[] {
  const hit = cache.get(text)
  if (hit) return hit
  const out = tagNow(text)
  if (cache.size > 400) cache.clear() // a reply redraws many times while it streams
  cache.set(text, out)
  return out
}

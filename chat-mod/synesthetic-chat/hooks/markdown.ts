// A small line-level markdown reader: headings, bullets, quotes and paragraphs become styled
// rows; fenced code, tables, rules and anything with a link pass through to the app's own
// Markdown element untouched.

export type Emph = { start: number; end: number; style: 'b' | 'i' | 'code' }

export type Piece =
  | { kind: 'raw'; text: string }
  | { kind: 'gap' }
  | { kind: 'row'; row: 'heading' | 'para' | 'item' | 'quote'; level: number; marker: string; text: string; emph: Emph[] }

const TOKEN_SRC = '(`[^`\\n]+`|\\*\\*\\*[^*\\n]+\\*\\*\\*|\\*\\*[^*\\n]+\\*\\*|\\*[^*\\s][^*\\n]*?\\*)'

export function parseInline(src: string): { text: string; emph: Emph[] } {
  let text = ''
  const emph: Emph[] = []
  let pos = 0
  // a fresh regex per call: the nested call below must not reset this loop's position
  const TOKEN = new RegExp(TOKEN_SRC, 'g')
  let m: RegExpExecArray | null
  while ((m = TOKEN.exec(src)) !== null) {
    text += src.slice(pos, m.index)
    const tok = m[0]
    const start = text.length
    if (tok.startsWith('`')) {
      text += tok.slice(1, -1)
      emph.push({ start, end: text.length, style: 'code' })
    } else {
      const n = tok.startsWith('***') ? 3 : tok.startsWith('**') ? 2 : 1
      const inner = parseInline(tok.slice(n, -n))
      text += inner.text
      for (const e of inner.emph) emph.push({ start: e.start + start, end: e.end + start, style: e.style })
      if (n >= 2) emph.push({ start, end: text.length, style: 'b' })
      if (n === 1 || n === 3) emph.push({ start, end: text.length, style: 'i' })
    }
    pos = m.index + tok.length
  }
  text += src.slice(pos)
  return { text, emph }
}

const FENCE = /^\s{0,3}(```|~~~)/
const HEADING = /^(#{1,6})\s+(.*?)\s*#*\s*$/
const BULLET = /^(\s*)([-*+]|\d{1,3}[.)])\s+(.*)$/
const QUOTE = /^\s{0,3}>\s?(.*)$/
const RULE = /^\s{0,3}([-*_])(\s*\1){2,}\s*$/
const TABLE = /^\s*\|/
// lines with a link or an html tag keep the app's own drawing, so links stay clickable
const HAS_LINK = /\]\(|<\/?[a-z]|https?:\/\//i

function needsRaw(line: string): boolean {
  return HAS_LINK.test(line)
}

export function splitMessage(src: string): Piece[] {
  const lines = src.replace(/\r\n?/g, '\n').split('\n')
  const out: Piece[] = []
  let raw: string[] = []
  let para: string[] = []
  let fence: string | null = null

  const flushRaw = () => {
    if (raw.length) out.push({ kind: 'raw', text: raw.join('\n') })
    raw = []
  }
  const flushPara = () => {
    if (!para.length) return
    const { text, emph } = parseInline(para.join(' '))
    out.push({ kind: 'row', row: 'para', level: 0, marker: '', text, emph })
    para = []
  }

  for (const line of lines) {
    if (fence !== null) {
      raw.push(line)
      if (line.trim().startsWith(fence)) {
        fence = null
        flushRaw()
      }
      continue
    }
    const f = FENCE.exec(line)
    if (f) {
      flushPara()
      raw.push(line)
      fence = f[1]
      continue
    }
    if (TABLE.test(line) || RULE.test(line) || needsRaw(line)) {
      flushPara()
      raw.push(line)
      continue
    }
    if (raw.length) flushRaw()
    if (line.trim() === '') {
      flushPara()
      out.push({ kind: 'gap' })
      continue
    }
    const h = HEADING.exec(line)
    if (h) {
      flushPara()
      const { text, emph } = parseInline(h[2])
      out.push({ kind: 'row', row: 'heading', level: h[1].length, marker: '', text, emph })
      continue
    }
    const b = BULLET.exec(line)
    if (b) {
      flushPara()
      const { text, emph } = parseInline(b[3])
      const ordered = /\d/.test(b[2])
      out.push({
        kind: 'row',
        row: 'item',
        level: Math.floor(b[1].replace(/\t/g, '  ').length / 2),
        marker: ordered ? b[2] : '•',
        text,
        emph
      })
      continue
    }
    const q = QUOTE.exec(line)
    if (q) {
      flushPara()
      const { text, emph } = parseInline(q[1])
      out.push({ kind: 'row', row: 'quote', level: 0, marker: '', text, emph })
      continue
    }
    const last = out[out.length - 1]
    if (para.length === 0 && last && last.kind === 'row' && last.row === 'item' && /^\s+\S/.test(line)) {
      // continuation of the previous bullet
      const { text, emph } = parseInline(line.trim())
      const base = last.text.length + 1
      last.text += ' ' + text
      for (const e of emph) last.emph.push({ start: e.start + base, end: e.end + base, style: e.style })
      continue
    }
    para.push(line.trim())
  }
  flushPara()
  flushRaw()
  while (out.length && out[out.length - 1].kind === 'gap') out.pop()
  return out
}

export type Run = { text: string; bold: boolean; italic: boolean; code: boolean; cat: string | null }

export function toRuns(
  text: string,
  emph: Emph[],
  spans: Array<{ start: number; end: number; cat: string }>
): Run[] {
  const cuts = new Set<number>([0, text.length])
  for (const e of emph) {
    cuts.add(Math.max(0, Math.min(text.length, e.start)))
    cuts.add(Math.max(0, Math.min(text.length, e.end)))
  }
  for (const s of spans) {
    cuts.add(s.start)
    cuts.add(s.end)
  }
  const pts = [...cuts].sort((a, b) => a - b)
  const runs: Run[] = []
  for (let i = 0; i + 1 < pts.length; i++) {
    const a = pts[i]
    const b = pts[i + 1]
    if (b <= a) continue
    const run: Run = { text: text.slice(a, b), bold: false, italic: false, code: false, cat: null }
    for (const e of emph) {
      if (e.start <= a && e.end >= b) {
        if (e.style === 'b') run.bold = true
        else if (e.style === 'i') run.italic = true
        else run.code = true
      }
    }
    for (const s of spans) {
      if (s.start <= a && s.end >= b) run.cat = s.cat
    }
    const prev = runs[runs.length - 1]
    if (prev && prev.bold === run.bold && prev.italic === run.italic && prev.code === run.code && prev.cat === run.cat) {
      prev.text += run.text
    } else {
      runs.push(run)
    }
  }
  return runs
}

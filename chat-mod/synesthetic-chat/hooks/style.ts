// Turns a category plus the person's options into Text props. With the Editor's looks loaded
// (remote.ts), those decide colors, cues, the highlight style and which categories are off.
import { GRAMMAR, LENS } from './lens'
import type { GrammarCategory, LensCategory } from './lens'
import type { BankWord, ChatStyle, Look } from './remote'

export type Options = {
  mode: 'a' | 'b' | 'c'
  theme: 'dark' | 'light'
  palette: 'default' | 'cb'
  grammar: boolean
  off: Set<string>
}

export type StyleProps = {
  color?: string
  backgroundColor?: string
  weight?: 'bold'
  dimColor?: boolean
  italic?: boolean
  underline?: boolean
  mono?: boolean
  tabular?: boolean
}

const BG = { dark: '#14161b', light: '#fbfbf8' }
const BY_NAME = new Map<string, LensCategory>(LENS.map(c => [c.name, c]))
const GRAMMAR_BY_NAME = new Map<string, GrammarCategory>(GRAMMAR.map(c => [c.name, c]))

let STYLE: ChatStyle | null = null

/** The Editor's looks to draw with from now on (null: the lens as shipped). */
export function setStyle(s: ChatStyle | null): void {
  STYLE = s
}

export function currentStyle(): ChatStyle | null {
  return STYLE
}

function rgb(hex: string): [number, number, number] {
  const h = hex.replace('#', '')
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)]
}

function toHex(v: [number, number, number]): string {
  return '#' + v.map(n => Math.round(n).toString(16).padStart(2, '0')).join('')
}

function lin(c: number): number {
  const s = c / 255
  return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4)
}

export function luminance(hex: string): number {
  const [r, g, b] = rgb(hex)
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
}

/** Text color readable on a chip filled with `hex`. */
export function onColor(hex: string): string {
  const l = luminance(hex)
  const dark = (l + 0.05) / (luminance('#101216') + 0.05)
  const light = 1.05 / (l + 0.05)
  return dark >= light ? '#101216' : '#ffffff'
}

/** `hex` blended over a background at `alpha`, so a tint reads as the same hue on that theme. */
export function tint(hex: string, bg: string, alpha: number): string {
  const a = rgb(hex)
  const b = rgb(bg)
  return toHex([a[0] * alpha + b[0] * (1 - alpha), a[1] * alpha + b[1] * (1 - alpha), a[2] * alpha + b[2] * (1 - alpha)])
}

/** The options as the Editor's looks adjust them: its theme, palette, highlight style and switches. */
export function effectiveOptions(o: Options): Options {
  if (!STYLE) return o
  const out: Options = { ...o, off: new Set(o.off) }
  if (STYLE.theme === 'dark' || STYLE.theme === 'light') out.theme = STYLE.theme
  if (STYLE.palette === 'default' || STYLE.palette === 'cb') out.palette = STYLE.palette
  if (STYLE.mode === 'a' || STYLE.mode === 'b' || STYLE.mode === 'c') out.mode = STYLE.mode
  else if (STYLE.mode === 'd') out.mode = 'a' // underline-only: colored text with its underline
  // the Editor's switches decide: a category it left on is on, even one the lens starts off
  for (const c of LENS) if (c.defaultOff && STYLE.off.indexOf(c.name) < 0) out.off.delete(c.name)
  for (const n of STYLE.off) out.off.add(n)
  return out
}

export function categoryColor(cat: { name: string; colors: LensCategory['colors'] }, o: Options): string {
  if (o.palette === 'cb') return cat.colors[o.theme === 'dark' ? 'cb_dark' : 'cb_light']
  const own = STYLE && STYLE.colors[cat.name] && STYLE.colors[cat.name][o.theme]
  return own || cat.colors[o.theme]
}

type Cues = { bold: boolean; thin: boolean; italic: boolean; underline: boolean; caps: boolean }

function cues(cat: { name: string; font: string; weight: number; underline: string; case: string }): Cues {
  const l: Look = (STYLE && STYLE.look[cat.name]) || {}
  const bold = l.bold !== undefined ? l.bold : cat.weight >= 600
  const thin = !bold && (l.thin !== undefined ? l.thin : cat.weight > 0 && cat.weight <= 300)
  const italic = l.italic !== undefined ? l.italic : cat.font === 'italic'
  const underline = (l.underline !== undefined ? l.underline : cat.underline) !== 'none'
  const caps = (l.case !== undefined ? l.case : cat.case) === 'upper'
  return { bold, thin, italic, underline, caps }
}

/** Whether a category's words are drawn in ALL CAPS (the Editor's choice, else the lens's). */
export function capsFor(catName: string): boolean {
  const cat = BY_NAME.get(catName) || GRAMMAR_BY_NAME.get(catName)
  return cat ? cues(cat).caps : false
}

export function styleFor(catName: string, o: Options): StyleProps | null {
  if (o.off.has(catName)) return null
  const word = GRAMMAR_BY_NAME.get(catName)
  if (word) {
    // a grammar word: a muted tint plus its own letter shape, never a fill, in every style
    const k = cues(word)
    const g: StyleProps = { color: categoryColor(word, o) }
    if (k.bold) g.weight = 'bold'
    if (k.thin) g.dimColor = true
    if (k.italic) g.italic = true
    if (k.underline) g.underline = true
    return g
  }
  const cat = BY_NAME.get(catName)
  if (!cat) return null
  const color = categoryColor(cat, o)
  const k = cues(cat)
  const p: StyleProps = {}
  if (o.mode === 'a') {
    p.color = color
  } else if (o.mode === 'b') {
    p.backgroundColor = color
    p.color = onColor(color)
  } else {
    p.color = color
    p.backgroundColor = tint(color, BG[o.theme], 0.24)
  }
  if (k.bold) p.weight = 'bold'
  if (k.thin) p.dimColor = true
  if (k.italic) p.italic = true
  if (cat.font === 'mono') p.mono = true
  if (cat.font === 'tabular') p.tabular = true
  if (k.underline && o.mode !== 'b') p.underline = true
  return p
}

/** A Word Bank entry's own look (an entry that counts as a category is drawn as that category). */
export function bankStyle(w: BankWord, o: Options): StyleProps | null {
  if (w.cat) return styleFor(w.cat, o)
  const p: StyleProps = {}
  if (w.color) p.color = w.color
  if (w.bg) {
    p.backgroundColor = w.bg
    if (!w.color) p.color = onColor(w.bg)
  }
  if (w.bold) p.weight = 'bold'
  if (w.italic) p.italic = true
  if (w.underline) p.underline = true
  return p
}

export function parseOptions(raw: Record<string, unknown> | undefined): Options {
  const pick = <T extends string>(v: unknown, allowed: readonly T[], dflt: T): T =>
    typeof v === 'string' && (allowed as readonly string[]).includes(v) ? (v as T) : dflt
  const offRaw = typeof raw?.off === 'string' ? raw.off : LENS.filter(c => c.defaultOff).map(c => c.name).join(',')
  return {
    mode: pick(raw?.mode, ['a', 'b', 'c'] as const, 'c'),
    theme: pick(raw?.theme, ['dark', 'light'] as const, 'dark'),
    palette: pick(raw?.palette, ['default', 'cb'] as const, 'default'),
    grammar: pick(raw?.grammar, ['on', 'off'] as const, 'on') === 'on',
    off: new Set(offRaw.split(',').map(s => s.trim()).filter(Boolean))
  }
}

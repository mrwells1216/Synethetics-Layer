// Turns a category plus the person's options into Text props.
import { LENS } from './lens'
import type { LensCategory } from './lens'

export type Options = { mode: 'a' | 'b' | 'c'; theme: 'dark' | 'light'; palette: 'default' | 'cb'; off: Set<string> }

export type StyleProps = {
  color?: string
  backgroundColor?: string
  weight?: 'bold'
  italic?: boolean
  underline?: boolean
  mono?: boolean
  tabular?: boolean
}

const BG = { dark: '#14161b', light: '#fbfbf8' }
const BY_NAME = new Map<string, LensCategory>(LENS.map(c => [c.name, c]))

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

export function categoryColor(cat: LensCategory, o: Options): string {
  const key = (o.palette === 'cb' ? (o.theme === 'dark' ? 'cb_dark' : 'cb_light') : o.theme) as keyof LensCategory['colors']
  return cat.colors[key]
}

export function styleFor(catName: string, o: Options): StyleProps | null {
  const cat = BY_NAME.get(catName)
  if (!cat || o.off.has(catName)) return null
  const color = categoryColor(cat, o)
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
  if (cat.weight >= 600) p.weight = 'bold'
  if (cat.font === 'italic') p.italic = true
  if (cat.font === 'mono') p.mono = true
  if (cat.font === 'tabular') p.tabular = true
  if (cat.underline !== 'none' && o.mode !== 'b') p.underline = true
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
    off: new Set(offRaw.split(',').map(s => s.trim()).filter(Boolean))
  }
}

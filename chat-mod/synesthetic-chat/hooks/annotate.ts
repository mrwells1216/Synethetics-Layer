// Port of synesthetic/annotate.py: content-type spans, lower priority number wins an overlap.
import { tag } from './library'
import { GRAMMAR, LENS } from './lens'
import type { LensCategory } from './lens'

export type Span = { start: number; end: number; cat: string }

type Compiled = { cat: LensCategory; res: RegExp[] }

let compiled: Compiled[] | null = null

function compile(): Compiled[] {
  if (compiled === null) {
    compiled = LENS.map(cat => ({
      cat,
      res: cat.patterns.map(p => new RegExp(p, 'gd' + cat.flags)) // d: group offsets via m.indices
    }))
  }
  return compiled
}

export function annotate(text: string, off: ReadonlySet<string> = new Set()): Span[] {
  if (!text) return []
  const cands: Array<[number, number, number, string]> = []
  for (const { cat, res } of compile()) {
    if (off.has(cat.name)) continue
    for (const re of res) {
      re.lastIndex = 0
      let m: RegExpExecArray | null
      while ((m = re.exec(text)) !== null) {
        if (m[0].length === 0) {
          re.lastIndex += 1
          continue
        }
        let s = m.index
        let e = s + m[0].length
        const g1 = m.indices?.[1] // the group's real position, as Python's m.span(1)
        if (g1 && g1[1] > g1[0]) [s, e] = g1
        cands.push([cat.priority, s, -(e - s), cat.name + '\u0000' + e])
      }
    }
  }
  cands.sort((a, b) => a[0] - b[0] || a[1] - b[1] || a[2] - b[2])
  const taken = new Uint8Array(text.length)
  const out: Span[] = []
  for (const [, s, , tag] of cands) {
    const [name, endStr] = tag.split('\u0000')
    const e = Number(endStr)
    let free = true
    for (let i = s; i < e; i++) {
      if (taken[i]) {
        free = false
        break
      }
    }
    if (!free) continue
    for (let i = s; i < e; i++) taken[i] = 1
    out.push({ start: s, end: e, cat: name })
  }
  out.sort((a, b) => a.start - b.start)
  return out
}

const KIND_CAT = new Map<string, string>(GRAMMAR.map(g => [g.kind, g.name]))

/** Content spans plus the grammar words around them. Grammar never sits under a content span
 *  or inside a `blocked` range (inline code). Port of synesthetic/layers.py. */
export function annotateAll(
  text: string,
  off: ReadonlySet<string> = new Set(),
  grammar = true,
  blocked: ReadonlyArray<readonly [number, number]> = []
): Span[] {
  const content = annotate(text, off)
  if (!grammar || !text) return content
  const walls: Array<readonly [number, number]> = content.map(s => [s.start, s.end] as const)
  for (const b of blocked) walls.push(b)
  const out: Span[] = content.slice()
  for (const g of tag(text)) {
    const cat = KIND_CAT.get(g.kind)
    if (!cat || off.has(cat)) continue
    let parts: Array<[number, number]> = [[g.start, g.end]]
    for (const [ws, we] of walls) {
      const next: Array<[number, number]> = []
      for (const [s, e] of parts) {
        if (we <= s || ws >= e) {
          next.push([s, e])
          continue
        }
        if (s < ws) next.push([s, ws])
        if (we < e) next.push([we, e])
      }
      parts = next
      if (!parts.length) break
    }
    for (const [s, e] of parts) if (e > s) out.push({ start: s, end: e, cat })
  }
  out.sort((a, b) => a.start - b.start)
  return out
}

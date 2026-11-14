// Port of synesthetic/annotate.py: content-type spans, lower priority number wins an overlap.
import { LENS } from './lens'
import type { LensCategory } from './lens'

export type Span = { start: number; end: number; cat: string }

type Compiled = { cat: LensCategory; res: RegExp[] }

let compiled: Compiled[] | null = null

function compile(): Compiled[] {
  if (compiled === null) {
    compiled = LENS.map(cat => ({
      cat,
      res: cat.patterns.map(p => new RegExp(p, 'g' + cat.flags))
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
        if (m.length > 1 && m[1] !== undefined && m[1].length > 0) {
          s = m.index + m[0].indexOf(m[1])
          e = s + m[1].length
        }
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

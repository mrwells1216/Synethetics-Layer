import type { Register } from 'claude-code'

import { annotateAll } from './annotate'
import { splitMessage, toRuns } from './markdown'
import type { Piece, Run } from './markdown'
import { loadStyle } from './remote'
import type { BankWord } from './remote'
import { bankStyle, capsFor, currentStyle, effectiveOptions, parseOptions, setStyle, styleFor } from './style'
import type { Options } from './style'

type RowPiece = Extract<Piece, { kind: 'row' }>
type Host = Parameters<typeof loadStyle>[0]

// the Editor's looks: read once per session (the last ones seen are kept, so offline still draws them)
let loading: Promise<void> | null = null
function load($: Host, again = false): Promise<void> {
  if (again || !loading) loading = loadStyle($).then(setStyle, () => undefined)
  return loading
}

function runsOf(p: RowPiece, o: Options, words: BankWord[]): { runs: Run[]; styled: boolean } {
  // grammar words stay out of inline code: code keeps its own look
  const code = p.emph.filter(e => e.style === 'code').map(e => [e.start, e.end] as const)
  const spans = p.row === 'heading' ? [] : annotateAll(p.text, o.off, o.grammar, code, words)
  const runs = toRuns(p.text, p.emph, spans)
  return { runs, styled: spans.length > 0 }
}

export const register: Register = (on, options) => {
  const base = parseOptions(options as Record<string, unknown> | undefined)

  on('session.start', async ($, e, next) => {
    void load($, true)
    return next(e)
  })

  on('ui.render', { component: 'AssistantMessage' }, async ($, e, next) => {
    if (e.props.isSummary) return next(e)
    await load($)
    const o = effectiveOptions(base)
    const style = currentStyle()
    const words = style ? style.words : []

    const pieces = splitMessage(e.props.text)
    const rows = pieces.map(p => (p.kind === 'row' ? runsOf(p, o, words) : null))
    // Nothing detected in this block: leave the app's own drawing alone.
    if (!rows.some(r => r !== null && r.styled)) return next(e)

    const { Box, Text, Markdown } = $.ui.resolve(e)

    const styleOf = (cat: string) => {
      if (cat.startsWith('wb-')) {
        const w = words[Number(cat.slice(3))]
        return w ? { style: bankStyle(w, o), caps: !!w.caps } : { style: null, caps: false }
      }
      return { style: styleFor(cat, o), caps: capsFor(cat) }
    }

    const draw = (runs: Run[], base: { weight?: 'bold'; italic?: boolean }) =>
      runs.map((r, i) => {
        const { style, caps } = r.cat ? styleOf(r.cat) : { style: null, caps: false }
        return (
          <Text
            key={String(i)}
            {...(style ?? {})}
            weight={style?.weight ?? (r.bold || base.weight ? 'bold' : undefined)}
            italic={style?.italic ?? (r.italic || base.italic ? true : undefined)}
            mono={style?.mono ?? (r.code ? true : undefined)}
          >
            {style && caps ? r.text.toUpperCase() : r.text}
          </Text>
        )
      })

    const children = pieces.map((p, i) => {
      if (p.kind === 'raw') return <Markdown key={String(i)} text={p.text} />
      if (p.kind === 'gap') return <Text key={String(i)}> </Text>
      const { runs } = rows[i] as { runs: Run[]; styled: boolean }
      if (p.row === 'heading') {
        return (
          <Text key={String(i)} weight="bold" size={p.level <= 2 ? 'heading' : 'body'}>
            {draw(runs, { weight: 'bold' })}
          </Text>
        )
      }
      if (p.row === 'item') {
        return (
          <Box key={String(i)} flexDirection="row" paddingLeft={p.level * 2}>
            <Text dimColor>{p.marker} </Text>
            <Text>{draw(runs, {})}</Text>
          </Box>
        )
      }
      if (p.row === 'quote') {
        return (
          <Box key={String(i)} flexDirection="row">
            <Text dimColor>▎ </Text>
            <Text italic>{draw(runs, { italic: true })}</Text>
          </Box>
        )
      }
      return <Text key={String(i)}>{draw(runs, {})}</Text>
    })

    return <Box flexDirection="column">{children}</Box>
  })
}

import type { Register } from 'claude-code'

import { annotateAll } from './annotate'
import { splitMessage, toRuns } from './markdown'
import type { Piece, Run } from './markdown'
import { parseOptions, styleFor } from './style'
import type { Options } from './style'

type RowPiece = Extract<Piece, { kind: 'row' }>

function runsOf(p: RowPiece, o: Options): { runs: Run[]; styled: boolean } {
  // grammar words stay out of inline code: code keeps its own look
  const code = p.emph.filter(e => e.style === 'code').map(e => [e.start, e.end] as const)
  const spans = p.row === 'heading' ? [] : annotateAll(p.text, o.off, o.grammar, code)
  const runs = toRuns(p.text, p.emph, spans)
  return { runs, styled: spans.length > 0 }
}

export const register: Register = (on, options) => {
  const o = parseOptions(options as Record<string, unknown> | undefined)

  on('ui.render', { component: 'AssistantMessage' }, async ($, e, next) => {
    if (e.props.isSummary) return next(e)

    const pieces = splitMessage(e.props.text)
    const rows = pieces.map(p => (p.kind === 'row' ? runsOf(p, o) : null))
    // Nothing detected in this block: leave the app's own drawing alone.
    if (!rows.some(r => r !== null && r.styled)) return next(e)

    const { Box, Text, Markdown } = $.ui.resolve(e)

    const draw = (runs: Run[], base: { weight?: 'bold'; italic?: boolean }) =>
      runs.map((r, i) => {
        const style = r.cat ? styleFor(r.cat, o) : null
        return (
          <Text
            key={String(i)}
            {...(style ?? {})}
            weight={style?.weight ?? (r.bold || base.weight ? 'bold' : undefined)}
            italic={style?.italic ?? (r.italic || base.italic ? true : undefined)}
            mono={style?.mono ?? (r.code ? true : undefined)}
          >
            {r.text}
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

// The Editor's looks, as the app stores them for this add-on: colors, highlight style, each
// category's look, the categories switched off and the Word Bank. They are read from this
// computer's app folder (the app running here writes style.json there) and from the hosted site
// (remote.json there holds its address and the dev key the owner paired with), newest wins, and the
// last one seen is kept in the plugin's store so a session offline still draws them.

export type Look = { case?: string; scale?: number; bold?: boolean; thin?: boolean; italic?: boolean; underline?: string; ul?: string }
export type BankWord = { word: string; cat?: string; color?: string; bg?: string; caps?: boolean; bold?: boolean; italic?: boolean; underline?: boolean; size?: number }
export type ChatStyle = {
  colors: Record<string, { dark?: string; light?: string }>
  mode?: string
  theme?: string
  palette?: string
  look: Record<string, Look>
  off: string[]
  words: BankWord[]
  updated?: string
}

type Host = {
  store: { get: (k: string) => Promise<unknown>; set: (k: string, v: unknown) => Promise<void> }
  fs: { read: (p: string) => Promise<string>; exists: (p: string) => Promise<boolean> }
  http: { fetch: (url: string, init?: { method?: string; headers?: Record<string, string>; body?: string }) => Promise<{ ok: boolean; text: string }> }
  process: { run: (argv: readonly string[], init?: { timeoutMs?: number }) => Promise<{ exitCode: number; stdout: string }> }
}

function clean(raw: unknown): ChatStyle | null {
  if (!raw || typeof raw !== 'object') return null
  const r = raw as Record<string, unknown>
  const hex = (v: unknown) => (typeof v === 'string' && /^#[0-9a-f]{6}$/i.test(v) ? v.toLowerCase() : undefined)
  const colors: ChatStyle['colors'] = {}
  if (r.colors && typeof r.colors === 'object') {
    for (const [name, pair] of Object.entries(r.colors as Record<string, unknown>)) {
      if (!pair || typeof pair !== 'object') continue
      const p = pair as Record<string, unknown>
      const out: { dark?: string; light?: string } = {}
      const d = hex(p.dark)
      const l = hex(p.light)
      if (d) out.dark = d
      if (l) out.light = l
      if (d || l) colors[name] = out
    }
  }
  const look: ChatStyle['look'] = {}
  if (r.look && typeof r.look === 'object') {
    for (const [name, v] of Object.entries(r.look as Record<string, unknown>)) {
      if (!v || typeof v !== 'object') continue
      const o = v as Record<string, unknown>
      const item: Look = {}
      if (o.case === 'upper' || o.case === 'normal') item.case = o.case
      if (typeof o.scale === 'number') item.scale = o.scale
      for (const k of ['bold', 'thin', 'italic'] as const) if (typeof o[k] === 'boolean') item[k] = o[k] as boolean
      if (typeof o.underline === 'string') item.underline = o.underline
      const ul = hex(o.ul)
      if (ul) item.ul = ul
      if (Object.keys(item).length) look[name] = item
    }
  }
  const words: BankWord[] = []
  if (Array.isArray(r.words)) {
    for (const w of r.words.slice(0, 200)) {
      if (!w || typeof w !== 'object' || typeof (w as BankWord).word !== 'string') continue
      const e = w as Record<string, unknown>
      const b: BankWord = { word: String(e.word).trim().slice(0, 80) }
      if (!b.word) continue
      if (typeof e.cat === 'string') b.cat = e.cat
      const c = hex(e.color)
      const bg = hex(e.bg)
      if (c) b.color = c
      if (bg) b.bg = bg
      for (const k of ['caps', 'bold', 'italic', 'underline'] as const) if (e[k] === true) b[k] = true
      if (typeof e.size === 'number') b.size = e.size
      words.push(b)
    }
  }
  const pick = (v: unknown, allowed: string[]) => (typeof v === 'string' && allowed.includes(v) ? v : undefined)
  return {
    colors,
    mode: pick(r.mode, ['a', 'b', 'c', 'd']),
    theme: pick(r.theme, ['auto', 'dark', 'light']),
    palette: pick(r.palette, ['default', 'cb']),
    look,
    off: Array.isArray(r.off) ? r.off.filter((x): x is string => typeof x === 'string') : [],
    words,
    updated: typeof r.updated === 'string' ? r.updated : undefined
  }
}

async function dataDir($: Host): Promise<string | null> {
  // the app's folder: %LOCALAPPDATA%\SynestheticLayer on Windows, ~/.local/share/synesthetic-layer elsewhere
  const tries: Array<[string[], (out: string) => string]> = [
    [['cmd', '/c', 'echo %LOCALAPPDATA%'], out => out.trim() + '\\SynestheticLayer'],
    [['sh', '-c', 'echo "$HOME"'], out => out.trim() + '/.local/share/synesthetic-layer']
  ]
  for (const [argv, make] of tries) {
    try {
      const r = await $.process.run(argv, { timeoutMs: 5000 })
      const out = r.stdout || ''
      if (r.exitCode === 0 && out.trim() && !/%LOCALAPPDATA%/.test(out)) return make(out)
    } catch {
      /* not this platform */
    }
  }
  return null
}

async function readJson($: Host, path: string): Promise<unknown> {
  try {
    if (!(await $.fs.exists(path))) return null
    return JSON.parse(await $.fs.read(path))
  } catch {
    return null
  }
}

/** The newest looks the owner saved: the computer's own file, the hosted site, or the last one kept. */
export async function loadStyle($: Host): Promise<ChatStyle | null> {
  let best: ChatStyle | null = clean(await $.store.get('style').catch(() => null))
  const consider = (s: ChatStyle | null) => {
    if (s && (!best || (s.updated || '') >= (best.updated || ''))) best = s
  }
  const dir = await dataDir($)
  if (dir) {
    consider(clean(await readJson($, dir + (dir.includes('\\') ? '\\' : '/') + 'style.json')))
    const remote = (await readJson($, dir + (dir.includes('\\') ? '\\' : '/') + 'remote.json')) as { url?: string; key?: string } | null
    if (remote && typeof remote.url === 'string' && typeof remote.key === 'string') {
      try {
        const r = await $.http.fetch(remote.url.replace(/\/$/, '') + '/api/style-get', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-App': '1', 'X-Dev-Key': remote.key },
          body: '{}'
        })
        if (r.ok) consider(clean((JSON.parse(r.text) as { style?: unknown }).style))
      } catch {
        /* offline: the kept one stands */
      }
    }
  }
  if (best) await $.store.set('style', best).catch(() => undefined)
  return best
}

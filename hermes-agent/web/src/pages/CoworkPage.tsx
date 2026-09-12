import { useEffect, useState } from "react"

interface Room { room: string; topic: string; members: number; created_at: string }

export default function CoworkPage() {
  const [rooms, setRooms] = useState<Room[]>([])
  const [newRoom, setNewRoom] = useState("")
  const [topic, setTopic] = useState("")
  const [status, setStatus] = useState<string>("")

  const load = async () => {
    try {
      const res = await fetch("/api/crowork/list")
      if (res.ok) {
        const j = await res.json()
        setRooms(j.rooms || [])
      } else {
        // fallback: try via shell API or show demo
        setRooms([])
      }
    } catch {
      setRooms([])
    }
  }

  useEffect(() => { void load() }, [])

  const create = async () => {
    if (!newRoom.trim()) return
    setStatus("Criando...")
    try {
      const res = await fetch("/api/crowork/create", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ room: newRoom.trim(), topic }) })
      if (res.ok) {
        setStatus(`Sala '${newRoom}' criada!`)
        setNewRoom(""); setTopic(""); void load()
      } else {
        setStatus("Criado localmente — use: hermes crowork create " + newRoom)
      }
    } catch {
      setStatus("Modo local: hermes crowork create " + newRoom)
    }
  }

  const copyInvite = (room: string) => {
    const txt = `hermes crowork join ${room}`
    navigator.clipboard.writeText(txt)
    setStatus(`Convite copiado: ${txt}`)
  }

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">👥 CROWORK — Salas Colaborativas</h1>
        <span className="text-xs px-2 py-1 rounded bg-[#0F3460] text-white">VMP-AI • Bento Workspace</span>
      </div>
      <p className="text-sm text-muted-foreground">Uma sala = um transcript + um PTY espelhado + presença ao vivo. Crie, compartilhe <code>hermes crowork join &lt;sala&gt;</code>, codem juntos. Dados em <code>HERMES_HOME/crowork/*.json</code></p>

      <div className="rounded-xl border p-4 space-y-3 bg-card">
        <h2 className="font-semibold">Nova sala</h2>
        <div className="flex flex-wrap gap-2">
          <input value={newRoom} onChange={e => setNewRoom(e.target.value)} placeholder="sala (ex: ampliagro-sprint)" className="flex-1 min-w-[200px] px-3 py-2 rounded border bg-background" />
          <input value={topic} onChange={e => setTopic(e.target.value)} placeholder="tópico (opcional)" className="flex-1 min-w-[220px] px-3 py-2 rounded border bg-background" />
          <button onClick={create} className="px-4 py-2 rounded bg-[#FF6B35] text-white font-medium hover:opacity-90">Criar</button>
        </div>
        {status && <div className="text-sm p-2 rounded bg-[#0F3460]/10 border">{status}</div>}
        <div className="text-xs text-muted-foreground">CLI: <code>hermes crowork create sala-01 &quot;Sprint Agro 5.0&quot;</code> • TUI: <code>/crowork create sala-01</code> • Aliases: <code>crow, cw</code></div>
      </div>

      <div className="rounded-xl border p-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold">Salas ativas</h2>
          <button onClick={() => void load()} className="text-xs px-3 py-1 rounded border">Atualizar</button>
        </div>
        {rooms.length === 0 ? (
          <div className="text-sm text-muted-foreground">Nenhuma sala ainda. Crie acima ou via CLI: <code>hermes crowork list</code></div>
        ) : (
          <div className="grid gap-2">
            {rooms.map(r => (
              <div key={r.room} className="flex items-center justify-between p-3 rounded border bg-card hover:bg-accent/50">
                <div>
                  <div className="font-medium">{r.room} <span className="text-xs text-muted-foreground">• {r.members} membros • {r.created_at}</span></div>
                  <div className="text-xs text-muted-foreground">{r.topic || "(sem tópico)"}</div>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => copyInvite(r.room)} className="text-xs px-3 py-1 rounded bg-[#0F3460] text-white">Copiar convite</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="rounded-xl border p-4 bg-amber-50/50 dark:bg-amber-950/20">
        <h3 className="font-semibold text-sm">Como funciona (todas as interfaces)</h3>
        <ul className="text-xs list-disc pl-5 space-y-1 mt-2">
          <li><b>CLI:</b> <code>hermes crowork join sala-01</code> — espelha terminal/PTY</li>
          <li><b>TUI:</b> <code>/crowork join sala-01</code> dentro do chat</li>
          <li><b>Web:</b> esta página (Cowork Board) — criar/listar/compartilhar</li>
          <li><b>Desktop:</b> plugin <code>hermes-crowork</code> — painel lateral com presença + chat por sala</li>
          <li><b>Gateway:</b> funciona de Telegram/Discord/Slack — convite é o mesmo comando</li>
        </ul>
      </div>
    </div>
  )
}

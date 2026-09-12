/**
 * hermes-crowork — Desktop plugin: presença + chat por sala CROWORK
 * Segue padrão hermes-bots: nanostore local, JSON-RPC via tui_gateway
 */
import { useEffect, useState } from "react"

type Room = { room: string; topic?: string; members: string[]; active?: string[] }

export function CroworkPanel() {
  const [rooms, setRooms] = useState<Room[]>([])
  const [selected, setSelected] = useState<string>("")
  const [status, setStatus] = useState<string>("")

  const refresh = async () => {
    try {
      // @ts-ignore — gateway client disponível no desktop
      const res = await (window as any).hermes?.invoke?.("crowork.list", {})
      if (res?.rooms) setRooms(res.rooms)
    } catch { /* fallback: lista via CLI handler */ }
  }

  useEffect(() => { void refresh(); const id = setInterval(refresh, 8000); return () => clearInterval(id) }, [])

  return (
    <div className="flex flex-col h-full p-3 gap-3">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-sm">👥 CROWORK</h3>
        <button onClick={() => void refresh()} className="text-xs px-2 py-1 border rounded">refresh</button>
      </div>
      <div className="text-xs text-muted-foreground">Salas compartilhadas — transcript + PTY espelhados</div>
      <div className="space-y-1 max-h-[40%] overflow-auto border rounded p-2">
        {rooms.length === 0 ? <div className="text-xs text-muted-foreground">Nenhuma sala. Crie com <code>hermes crowork create &lt;sala&gt;</code></div> :
          rooms.map(r => (
            <button key={r.room} onClick={() => setSelected(r.room)} className={`w-full text-left text-xs px-2 py-1.5 rounded border ${selected===r.room?"bg-[#0F3460] text-white":"hover:bg-accent"}`}>
              <div className="font-medium">{r.room}</div>
              <div className="opacity-70 truncate">{r.topic || "(sem tópico)"} • {r.members?.length||0} membros</div>
            </button>
          ))}
      </div>
      {selected && (
        <div className="flex-1 border rounded p-2 flex flex-col gap-2">
          <div className="text-xs font-medium">Sala: {selected} {status && <span className="opacity-60">— {status}</span>}</div>
          <div className="flex gap-2">
            <button onClick={async () => {
              try { await (window as any).hermes?.invoke?.("crowork.join", { room: selected }); setStatus("entrou!") } catch { setStatus("use: hermes crowork join " + selected) }
            }} className="text-xs px-3 py-1 rounded bg-[#FF6B35] text-white">Entrar</button>
            <button onClick={async () => {
              const txt = `hermes crowork join ${selected}`; await navigator.clipboard.writeText(txt); setStatus("convite copiado")
            }} className="text-xs px-3 py-1 rounded border">Copiar convite</button>
          </div>
          <div className="text-[11px] text-muted-foreground">TUI: <code>/crowork join {selected}</code> • CLI: <code>hermes cw join {selected}</code></div>
        </div>
      )}
      <div className="text-[11px] text-muted-foreground border-t pt-2">Aliases: <code>hermes crow, hermes cw</code> • Web: <code>/cowork</code> • Dados: <code>HERMES_HOME/crowork/*.json</code></div>
    </div>
  )
}

export default CroworkPanel

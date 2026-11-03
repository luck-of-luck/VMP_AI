import { spawn } from 'node:child_process';

const BIN = 'AppData/Local/Programs/codebase-memory-mcp/codebase-memory-mcp.exe';

function augment(tool: string, args: any): Promise<string> {
  return new Promise((resolve) => {
    const child = spawn(BIN, ['hook-augment'], {
      stdio: ['pipe', 'pipe', 'ignore'],
      env: { ...process.env, CBM_LOG_LEVEL: 'error' },
    });
    let out = '';
    child.stdout.on('data', (d) => (out += d.toString()));
    child.on('error', () => resolve(''));
    child.on('close', () => resolve(out));
    child.stdin.end(JSON.stringify({
      hook_event_name: 'PreToolUse',
      tool_name: tool,
      tool_input: args ?? {},
    }));
  });
}

export default {
  id: "cbm-augment",
  setup: async (api: any) => {
    if (api.tool?.hook) {
      try {
        api.tool.hook("execute.after", async (input: any) => {
          const tool = input?.tool === 'grep' ? 'Grep' : input?.tool === 'glob' ? 'Glob' : null;
          if (!tool) return;
          const extra = await augment(tool, input?.output?.args);
          if (extra && typeof input?.output?.output === 'string') {
            input.output.output += '\n' + extra;
          }
        });
      } catch {}
    }
  }
};
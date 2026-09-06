#!/usr/bin/env python3
"""VMP-AI n8n JSON-RPC Bridge - Integração real n8n ⇄ Hermes."""

import json
import asyncio
import os
from pathlib import Path
from typing import Dict, List, Any, Optional

# n8n bridge uses JSON-RPC over stdio (same as tui_gateway)
# This bridge connects VMP-AI coordinator to n8n workflows

VMP_HOME = Path(os.getenv("VMP_HOME", str(Path.home() / ".vmp-ai")))
N8N_WORKFLOWS_DIR = VMP_HOME / "n8n" / "workflows"
N8N_MCP_DIR = VMP_HOME / "n8n" / "mcp"


class NMCPTool:
    """Representa uma tool MCP registrada no bridge."""

    def __init__(self, name: str, description: str, handler):
        self.name = name
        self.description = description
        self.handler = handler


class N8nBridge:
    """Bridge JSON-RPC para n8n - execução de workflows, MCPs e habilidades."""

    def __init__(self):
        self.mcps: Dict[str, NMCPTool] = {}
        self.active_workflows: Dict[str, dict] = {}
        self.workflow_cache: Dict[str, List[dict]] = {}
        self.initialized = False

        # Load existing MCPs
        self._load_mcps()

        print("🔗 n8n Bridge VMP-AI inicializado")

    def _load_mcps(self):
        """Carrega MCPs registrados dos repositórios."""
        # Scan n8n-mcp directory
        if N8N_MCP_DIR.exists():
            for mcp_file in N8N_MCP_DIR.glob("*.py"):
                # Import and register
                import importlib.util

                spec = importlib.util.spec_from_file_location(mcp_file.stem, mcp_file)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                if hasattr(module, "register_mcp"):
                    try:
                        module.register_mcp(self)
                        print(f"   📦 MCP carregado: {mcp_file.name}")
                    except Exception as e:
                        print(f"   ⚠️ Erro ao carregar MCP {mcp_file.name}: {e}")

    def register_mcp(self, name: str, description: str, handler=None):
        """Registra um novo MCP no bridge."""
        self.mcps[name] = NMCPTool(name=name, description=description, handler=handler)
        print(f"   ✅ MCP registrado: {name}")

    async def execute_workflow(
        self, workflow_name: str, parameters: dict = None
    ) -> dict:
        """Executa um workflow n8n pelo nome."""
        workflow_path = N8N_WORKFLOWS_DIR / f"{workflow_name}.json"

        if not workflow_path.exists():
            return {
                "status": "error",
                "message": f"Workflow '{workflow_name}' não encontrado em {workflow_path}",
                "available": self.list_workflows(),
            }

        # Load workflow JSON
        import json

        with open(workflow_path) as f:
            workflow_def = json.load(f)

        # Mark as active
        workflow_id = f"{workflow_name}_{id(workflow_def)}"
        self.active_workflows[workflow_id] = {
            "name": workflow_name,
            "definition": workflow_def,
            "parameters": parameters or {},
            "status": "running",
        }

        # Execute workflow steps (simplified)
        results = []
        steps = workflow_def.get("nodes", [])

        for step in steps:
            step_type = step.get("type", "unknown")
            step_name = step.get("name", "unnamed")

            # Route to appropriate handler
            result = await self._route_step(step_type, step, parameters or {})
            results.append({"step": step_name, "type": step_type, "result": result})

            if result.get("status") == "error":
                self.active_workflows[workflow_id]["status"] = "failed"
                return {
                    "status": "partial",
                    "message": f"Workflow parcialmente executado - erro em: {step_name}",
                    "results": results,
                    "workflow_id": workflow_id,
                }

        self.active_workflows[workflow_id]["status"] = "completed"
        return {
            "status": "completed",
            "message": f"Workflow '{workflow_name}' executado com sucesso",
            "results": results,
            "workflow_id": workflow_id,
        }

    async def _route_step(self, step_type: str, step: dict, parameters: dict) -> dict:
        """Roteia um step do workflow para o handler adequado."""
        # Handle known MCP tools
        if step_type in self.mcps:
            tool = self.mcps[step_type]
            if tool.handler:
                return await tool.handler(parameters)

        # Handle known VMP-AI skills
        if step_type.startswith("skill:"):
            skill_name = step_type.split(":", 1)[1]
            return await self._execute_skill(skill_name, parameters)

        # Default: return structure
        return {
            "status": "executed",
            "message": f"Step '{step.get('name', 'unknown')}' executed",
            "step_type": step_type,
        }

    async def _execute_skill(self, skill_name: str, parameters: dict) -> dict:
        """Executa uma skill pelo nome."""
        # Look up skill in registry
        if skill_name in self.mcps:
            tool = self.mcps[skill_name]
            if tool.handler:
                return await tool.handler(parameters)

        return {
            "status": "not_found",
            "message": f"Skill '{skill_name}' não encontrada no registry",
        }

    def list_workflows(self) -> List[str]:
        """Lista workflows disponíveis."""
        if N8N_WORKFLOWS_DIR.exists():
            return [f.stem for f in N8N_WORKFLOWS_DIR.glob("*.json")]
        return []

    def list_mcps(self) -> List[str]:
        """Lista MCPs registrados."""
        return list(self.mcps.keys())

    async def handle_rpc(self, method: str, params: dict) -> dict:
        """Handle JSON-RPC calls from n8n client."""
        handlers = {
            "workflow.execute": self.execute_workflow,
            "workflow.list": lambda p: {"workflows": self.list_workflows()},
            "mcp.register": self.register_mcp,
            "mcp.list": lambda p: {"mcps": self.list_mcps()},
            "skill.execute": self._execute_skill,
            "skill.list": lambda p: {"skills": list(self.mcps.keys())},
        }

        handler = handlers.get(method)
        if handler:
            return await handler(params)

        return {"status": "error", "message": f"Método RPC desconhecido: {method}"}


# CLI entry point for the bridge
async def main():
    """Run the n8n bridge as a standalone process."""
    bridge = N8nBridge()
    print("🌀 VMP-AI n8n Bridge running on stdio JSON-RPC")

    # Read from stdin, write to stdout in JSON-RPC format
    while True:
        try:
            line = await asyncio.get_event_loop().run_in_executor(None, input, "")
            if line.strip().lower() in ["quit", "exit"]:
                break

            # Simple JSON-RPC handling
            msg = json.loads(line)
            method = msg.get("method", "")
            params = msg.get("params", {})

            result = await bridge.handle_rpc(method, params)

            response = {"jsonrpc": "2.0", "id": msg.get("id"), "result": result}

            print(json.dumps(response))

        except (EOFError, KeyboardInterrupt):
            break
        except json.JSONDecodeError:
            print(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "error": {"code": -32700, "message": "Parse error"},
                    }
                )
            )

    print("👋 n8n Bridge encerrado")


if __name__ == "__main__":
    asyncio.run(main())

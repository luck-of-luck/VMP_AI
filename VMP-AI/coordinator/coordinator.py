#!/usr/bin/env python3
"""VMP-AI Coordinator Agent - Agente coordenador soberano com Hermes."""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add hermes to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "hermes-agent"))

from hermes_constants import get_hermes_home, display_hermes_home
from hermes_cli.config import load_config
from model_tools import discover_builtin_tools, handle_function_call
from tools.registry import registry


class VMpCoordinator:
    """Coordenador VMP-AI que integra Hermes, n8n, IAs gratuitas, screen-reading."""

    def __init__(self):
        self.hermes_home = get_hermes_home()
        self.display_home = display_hermes_home()
        self.config = load_config()

        # Initialize Hermes tool discovery
        discover_builtin_tools()  # Auto-registers all tools from tools/*.py

        # VMP-AI specific state
        self.skills_registry = {}  # Skills carregados de todos os repos
        self.mcp_registry = {}  # MCPs registrados
        self.free_ia_catalog = {}  # Catálogo de IAs gratuitas
        self.api_registry = {}  # APIs dinâmicas geradas
        self.n8n_bridge = None  # Bridge para n8n
        self.screen_capabilities = {}  # Screen-reading capabilities

        # Load VMP-AI specific configs
        self._load_vmp_configs()

        print(f"✅ VMP-AI Coordinator inicializado")
        print(f"   📍 Hermes Home: {self.hermes_home}")
        print(f"   📍 Config: {self.display_home}/config.yaml")
        print(f"   🔧 Toolsets disponíveis: {list(registry._tools.keys())[:10]}...")

    def _load_vmp_configs(self):
        """Carrega configurações VMP-AI."""
        config_path = Path(self.display_home) / "config.yaml"
        if config_path.exists():
            import yaml

            with open(config_path) as f:
                user_config = yaml.safe_load(f)
            # Merge with defaults
            print(
                f"   ⚙️ Configurações carregadas: {user_config.get('model', {}).get('fallback_model', 'N/A')}"
            )

    async def process_task(self, task: str, context: dict = None) -> dict:
        """Processa uma tarefa pelo agente coordenador."""
        print(f"\n🎯 Tarefa recebida: {task[:80]}...")

        # Step 1: Contextualize with Hermes memory
        contextualized = await self._contextualize(task, context or {})

        # Step 2: Route to best available resource
        routed = await self._route_task(contextualized)

        # Step 3: Execute with appropriate tool/IA
        result = await self._execute_task(routed)

        # Step 4: Learn from result
        await self._learn(result)

        return result

    async def _contextualize(self, task: str, context: dict) -> dict:
        """Contexto usando Hermes memory + skills."""
        # Analyze task, extract intent, entities, required capabilities
        return {
            "intent": self._extract_intent(task),
            "entities": self._extract_entities(task),
            "required_capabilities": self._require_caps(task),
            "source_context": context,
        }

    def _extract_intent(self, task: str) -> str:
        """Extrai intenção da tarefa."""
        task_lower = task.lower()
        if any(k in task_lower for k in ["n8n", "workflow", "automação"]):
            return "n8n_workflow"
        elif any(k in task_lower for k in ["api", "gerar", "endpoint"]):
            return "api_generation"
        elif any(k in task_lower for k in ["screen", "tela", "vision", "ocr"]):
            return "screen_analysis"
        elif any(k in task_lower for k in ["skill", "mcp", "capacidade"]):
            return "skill_discovery"
        else:
            return "general_task"

    def _require_caps(self, task: str) -> list:
        """Retorna capacidades necessárias."""
        caps = []
        if "n8n" in task.lower():
            caps.append("n8n")
        if "api" in task.lower() or "endpoint" in task.lower():
            caps.append("api_gen")
        if "screen" in task.lower() or "tela" in task.lower():
            caps.append("screen_read")
        if "mcp" in task.lower():
            caps.append("mcp")
        if "skill" in task.lower():
            caps.append("skill")
        return caps or ["general"]

    async def _route_task(self, contextualized: dict) -> dict:
        """Roteia tarefa para o melhor recurso disponível."""
        intent = contextualized["intent"]
        caps = contextualized["required_capabilities"]

        routing = {"intent": intent, "selected_module": "general", "fallback_chain": []}

        if "n8n_workflow" in intent or "n8n" in caps:
            routing["selected_module"] = "n8n"
            routing["fallback_chain"] = ["coordinator", "cli", "manual"]
        elif "api_generation" in intent or "api_gen" in caps:
            routing["selected_module"] = "api_generator"
            routing["fallback_chain"] = ["coordinator", "manual"]
        elif "screen_analysis" in intent or "screen_read" in caps:
            routing["selected_module"] = "screen_analysis"
            routing["fallback_chain"] = ["browser_vision", "ocr_local", "coordinator"]
        elif "skill_discovery" in intent or "skill" in caps:
            routing["selected_module"] = "skill_discovery"
            routing["fallback_chain"] = ["skills_catalog", "mcp_catalog", "coordinator"]
        else:
            routing["selected_module"] = "coordinator"
            routing["fallback_chain"] = ["coordinator", "fallback_ia", "cli"]

        return routing

    async def _execute_task(self, routing: dict) -> dict:
        """Executa a tarefa pelo módulo selecionado."""
        module = routing["selected_module"]
        intent = routing["intent"]

        print(f"   🚀 Executando via: {module} (intenção: {intent})")

        if module == "n8n":
            return await self._execute_n8n(routing)
        elif module == "api_generator":
            return await self._execute_api_gen(routing)
        elif module == "screen_analysis":
            return await self._execute_screen(routing)
        elif module == "skill_discovery":
            return await self._execute_skill_discovery(routing)
        else:
            return await self._execute_coordinator(routing)

    async def _execute_n8n(self, routing: dict) -> dict:
        """Executa workflow n8n."""
        # Connect to n8n bridge, execute workflow
        return {
            "status": "n8n_executed",
            "message": "Workflow n8n em execução (bridge a ser conectado)",
            "module": "n8n",
        }

    async def _execute_api_gen(self, routing: dict) -> dict:
        """Gera API dinamicamente."""
        return {
            "status": "api_generation_started",
            "message": "Gerador de APIs VMP-AI acionado",
            "module": "api_generator",
        }

    async def _execute_screen(self, routing: dict) -> dict:
        """Screen-reading / vision."""
        return {
            "status": "screen_analysis_started",
            "message": "Screen-reading capabilities acionadas (browser_vision + OCR)",
            "module": "screen_analysis",
        }

    async def _execute_skill_discovery(self, routing: dict) -> dict:
        """Descobre skills de todos os repos."""
        # Scan user repos for skills
        skills = []
        # Integra repositórios conhecidos
        for repo_key in ["VORTEX_AI", "OmniRoute", "waha", "n8n-openapi-node"]:
            skills.append(f"skill_from_{repo_key}")

        return {
            "status": "skills_discovered",
            "skills_found": skills,
            "module": "skill_discovery",
        }

    async def _execute_coordinator(self, routing: dict) -> dict:
        """Execução geral pelo coordenador."""
        return {
            "status": "coordinator_executed",
            "message": "Tarefa processada pelo coordenador VMP-AI",
            "module": "coordinator",
        }

    async def _learn(self, result: dict):
        """Aprende com o resultado (memória Hermes)."""
        # Update Hermes memory with this interaction
        pass

    def list_available_skills(self) -> list:
        """Lista skills disponíveis de todos os repos."""
        return list(self.skills_registry.keys())

    def list_available_mcps(self) -> list:
        """Lista MCPs disponíveis."""
        return list(self.mcp_registry.keys())

    def get_free_ia_catalog(self) -> dict:
        """Retorna catálogo de IAs gratuitas."""
        return self.free_ia_catalog


# CLI entry point
async def main():
    """CLI para o coordenador VMP-AI."""
    print("""
╔═════════════════════════════════════════════════════════════════╗
║                 VMP-AI Coordinator Agent                        ║
║         Coordinator with Hermes, n8n, MCPs & Free IAs          ║
╚═════════════════════════════════════════════════════════════════╝
    """)

    coordinator = VMpCoordinator()

    while True:
        try:
            task = input("\n💬 Tarefa VMP-AI (ou 'quit'): ").strip()
            if task.lower() in ["quit", "exit", "q"]:
                print("👋 Encerrando VMP-AI Coordinator.")
                break

            if not task:
                continue

            result = await coordinator.process_task(task)
            print(f"\n✅ Resultado: {json.dumps(result, indent=2, ensure_ascii=False)}")

            # Show available options
            print(
                f"\n📦 Skills: {len(coordinator.list_available_skills())} disponíveis"
            )
            print(f"🔌 MCPs: {len(coordinator.list_available_mcps())} registrados")
            print(
                f"🆓 IAs Gratuitas: {list(coordinator.get_free_ia_catalog().keys())[:5]}..."
            )

        except KeyboardInterrupt:
            print("\n👋 Encerrando VMP-AI Coordinator.")
            break
        except Exception as e:
            print(f"\n❌ Erro: {e}")
            import traceback

            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

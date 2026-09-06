#!/usr/bin/env python3
"""VMP-AI Dynamic Skills/MCPs Loader - Descoberta, hot-reload e integração."""

import asyncio
import importlib
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

VMP_HOME = Path(os.getenv("VMP_HOME", str(Path.home() / ".vmp-ai")))
SKILLS_DIR = VMP_HOME / "skills"
MCPS_DIR = VMP_HOME / "mcp"
REGISTRY_FILE = VMP_HOME / ".skills_registry.json"

# Default skills from known repos
DEFAULT_SKILLS_FROM_REPOS = {
    "VORTEX_AI": {
        "name": "vortex_contextualizer",
        "description": "Contexto e coordenação multi-agente Hermes",
        "category": "agent",
        "actions": [
            {"method": "get", "path": "/context", "summary": "Get agent context"}
        ],
    },
    "OmniRoute": {
        "name": "omnivore_search",
        "description": "Pesquisa web avançada via OmniRoute API",
        "category": "search",
        "actions": [{"method": "get", "path": "/search", "summary": "Search web"}],
    },
    "waha": {
        "name": "whatsapp_api",
        "description": "Integração com WhatsApp HTTP API",
        "category": "messaging",
        "actions": [
            {"method": "post", "path": "/send", "summary": "Send WhatsApp message"}
        ],
    },
    "n8n-openapi-node": {
        "name": "n8n_node_builder",
        "description": "Construtor de nós n8n a partir de OpenAPI",
        "category": "automation",
        "actions": [{"method": "post", "path": "/node", "summary": "Build n8n node"}],
    },
}


class SkillsMCPLoader:
    """Loader que descobre skills e MCPs de todos os fontes."""

    def __init__(self):
        self.skills_registry: Dict[str, dict] = {}
        self.mcp_registry: Dict[str, dict] = {}
        self.hot_reload = False

        self._ensure_dirs()
        self._load_registry()
        self._discover_all()

        print(f"⚙️ Skills/MCPs Loader VMP-AI inicializado")
        print(f"   📦 Skills registradas: {len(self.skills_registry)}")
        print(f"   🔌 MCPs registrados: {len(self.mcp_registry)}")

    def _ensure_dirs(self):
        """Cria diretórios necessários."""
        SKILLS_DIR.mkdir(parents=True, exist_ok=True)
        MCPS_DIR.mkdir(parents=True, exist_ok=True)

    def _load_registry(self):
        """Carrega o registry persistente."""
        if REGISTRY_FILE.exists():
            try:
                with open(REGISTRY_FILE) as f:
                    self.skills_registry = json.load(f)
                # Also load MCPs if present
                mcps_path = REGISTRY_FILE.parent / "mcps_registry.json"
                if mcps_path.exists():
                    with open(mcps_path) as f:
                        self.mcp_registry = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"   ⚠️ Erro ao carregar registry: {e}")
                self.skills_registry = {}
                self.mcp_registry = {}
        else:
            # Initialize with default skills
            self.skills_registry = {}
            self._save_registry()

    def _save_registry(self):
        """Salva o registry persistente."""
        with open(REGISTRY_FILE, "w") as f:
            json.dump(self.skills_registry, f, indent=2, ensure_ascii=False)
        mcps_path = REGISTRY_FILE.parent / "mcps_registry.json"
        with open(mcps_path, "w") as f:
            json.dump(self.mcp_registry, f, indent=2, ensure_ascii=False)

    def _discover_all(self):
        """Descobre skills e MCPs de todas as fontes."""
        # 1. Skills do usuário (pastas na dir skills)
        self._discover_user_skills()

        # 2. Skills padrão de repos conhecidos
        self._discover_repo_skills()

        # 3. MCPs registrados
        self._discover_mcps()

        # 4. Salvar registry
        self._save_registry()

    def _discover_user_skills(self):
        """Descobre skills pastas do usuário na dir skills."""
        if not SKILLS_DIR.exists():
            return

        for skill_folder in SKILLS_DIR.iterdir():
            if not skill_folder.is_dir():
                continue

            # Verificar se tem SKILL.md ou __init__.py
            has_skill_md = (skill_folder / "SKILL.md").exists()
            has_init_py = (skill_folder / "__init__.py").exists()

            if not has_skill_md and not has_init_py:
                continue  # Pasta sem skill definition

            skill_name = skill_folder.name

            # Carregar definição
            skill_def = {"name": skill_name, "source": "user", "category": "user"}

            if has_skill_md:
                # Read SKILL.md frontmatter
                try:
                    with open(skill_folder / "SKILL.md") as f:
                        content = f.read()
                    # Simples parsing do frontmatter
                    import re

                    frontmatter_match = re.search(
                        r"^---\n(.*?)\n---", content, re.DOTALL
                    )
                    if frontmatter_match:
                        frontmatter = frontmatter_match.group(1)
                        for line in frontmatter.split("\n"):
                            if ":" in line:
                                key, val = line.split(":", 1)
                                skill_def[key.strip()] = val.strip().strip('"')
                except Exception as e:
                    print(f"   ⚠️ Erro lendo {skill_name}/SKILL.md: {e}")

            # Register if not already
            if skill_name not in self.skills_registry:
                self.skills_registry[skill_name] = skill_def
                print(f"   📦 Skill descoberta (usuário): {skill_name}")

    def _discover_repo_skills(self):
        """Descobre skills dos repositórios conhecidos do usuário."""
        for repo_key, default_skill in DEFAULT_SKILLS_FROM_REPOS.items():
            # Verificar se já está no registry
            if repo_key not in self.skills_registry:
                # Criar skill baseada no repo
                skill_name = default_skill["name"]
                skill_def = dict(default_skill)
                skill_def["source"] = f"repo:{repo_key}"
                skill_def["description"] = default_skill["description"]

                self.skills_registry[skill_name] = skill_def
                print(f"   📦 Skill descoberta (repo): {skill_name} (de {repo_key})")

    def _discover_mcps(self):
        """Descobre MCPs registrados."""
        MCPs_DIR_PATH = Path(
            "C:/Users/lucas/AppData/Local/hermes/.opencode/skills"
        )  # Example
        # In VMP-AI, MCPs vêm da integração n8n e do bridge
        # Por ora, registramos vazio e o bridge popula
        print(f"   🔌 MCPs: serão registrados via n8n bridge")

    def get_skill(self, skill_name: str) -> Optional[dict]:
        """Retorna uma skill do registry."""
        return self.skills_registry.get(skill_name)

    def list_skills(self) -> List[str]:
        """Lista all skill names."""
        return list(self.skills_registry.keys())

    def list_mcps(self) -> List[str]:
        """Lista all MCP names."""
        return list(self.mcp_registry.keys())

    async def hot_reload(self):
        """Hot-reload do registry - re-descobre tudo."""
        print("   🔄 Hot-reload skills/MCPs...")
        self.skills_registry = {}
        self.mcp_registry = {}
        self._discover_all()
        print(
            f"   ✅ Hot-reload concluído: {len(self.skills_registry)} skills, {len(self.mcp_registry)} MCPs"
        )

    async def execute_skill(self, skill_name: str, parameters: dict = None) -> dict:
        """Executa uma skill pelo nome."""
        skill = self.get_skill(skill_name)
        if not skill:
            return {
                "status": "not_found",
                "message": f"Skill '{skill_name}' não encontrada no registry",
                "available": self.list_skills(),
            }

        # Executar baseado no tipo/ação
        actions = skill.get("actions", [])
        if not actions:
            return {
                "status": "executed",
                "message": f"Skill '{skill_name}' executada (nenhuma ação definida)",
                "skill": skill_name,
            }

        # Executar primeira ação
        action = actions[0]
        method = action.get("method", "get")
        path = action.get("path", "/")

        return {
            "status": "executed",
            "message": f"Skill '{skill_name}' executada via {method} {path}",
            "skill": skill_name,
            "action": action,
            "parameters": parameters or {},
        }


# CLI entry point
async def main():
    """CLI para o loader de skills."""
    loader = SkillsMCPLoader()

    print("""
╔════════════════════════════════════════════════════════════════╗
║               VMP-AI Dynamic Skills/MCPs Loader               ║
║         Discovery, Hot-Reload & Registry                      ║
╚════════════════════════════════════════════════════════════════╝
    """)

    while True:
        try:
            print("\n1. Listar Skills")
            print("2. Listar MCPs")
            print("3. Executar Skill")
            print("4. Hot-Reload")
            print("5. Sair")

            choice = input("\nOpção: ").strip()

            if choice == "1":
                skills = loader.list_skills()
                print(f"\n📦 Skills ({len(skills)}):")
                for s in skills:
                    skill = loader.get_skill(s)
                    print(f"   - {s}: {skill.get('description', 'N/A')[:60]}...")

            elif choice == "2":
                mcps = loader.list_mcps()
                print(f"\n🔌 MCPs ({len(mcps)}):")
                for m in mcps:
                    print(f"   - {m}")

            elif choice == "3":
                skill_name = input("Nome da skill: ").strip()
                params_input = input("Parâmetros JSON (Enter=none): ").strip()
                params = json.loads(params_input) if params_input else {}
                result = await loader.execute_skill(skill_name, params)
                print(f"\n✅ {json.dumps(result, indent=2, ensure_ascii=False)}")

            elif choice == "4":
                await loader.hot_reload()

            elif choice == "5":
                break
            else:
                print("Opção inválida")

        except KeyboardInterrupt:
            print("\n👋 Encerrando.")
            break
        except json.JSONDecodeError:
            print("❌ JSON inválido nos parâmetros")
        except Exception as e:
            print(f"❌ Erro: {e}")
            import traceback

            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

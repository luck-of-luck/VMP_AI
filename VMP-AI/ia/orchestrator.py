#!/usr/bin/env python3
"""VMP-AI Free IA Orchestrator - Agregador de IAs gratuitas com fallback inteligente."""

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

VMP_HOME = Path(os.getenv("VMP_HOME", str(Path.home() / ".vmp-ai")))
IA_CONFIG = VMP_HOME / "ia" / "free_ias.yaml"
FALLBACK_CHAIN = VMP_HOME / "ia" / "fallback_chain.json"

IA_CATALOG = {
    "openrouter_free": {
        "name": "OpenRouter Free Tier",
        "description": "Free access to many models via OpenRouter",
        "provider": "openrouter",
        "free_tier": True,
        "models": [
            "openrouter/free",
            "z-ai/glm-5.2:free",
            "meta-llama/llama-3.3-70b-instruct:free",
            "qwen/qwen-2.5-72b-instruct:free",
        ],
        "category": "text",
        "max_tokens": 4096,
        "cost": 0.0,
    },
    "ollama_local": {
        "name": "Ollama Local",
        "description": "Local models via Ollama runtime",
        "provider": "ollama",
        "free_tier": True,
        "models": [
            "qwen2.5-coder:32b",
            "llama3.3:70b",
            "deepseek-r1:32b",
            "qwen2.5:14b",
        ],
        "category": "text/code",
        "max_tokens": 8192,
        "cost": 0.0,
        "require": ["ollama_running"],
    },
    "lm_studio_local": {
        "name": "LM Studio Local",
        "description": "Local models via LM Studio",
        "provider": "lm_studio",
        "free_tier": True,
        "models": [],  # User-loaded
        "category": "various",
        "max_tokens": 8192,
        "cost": 0.0,
        "require": ["lm_studio_running"],
    },
    "anthropic_claude": {
        "name": "Claude Sonnet 4 (Free Tier)",
        "provider": "anthropic",
        "free_tier": True,
        "models": ["claude-sonnet-4-6"],
        "category": "text",
        "max_tokens": 4096,
        "cost": 0.0,  # Free tier limited
    },
    "google_gemini": {
        "name": "Gemini 1.5 Flash (Free)",
        "provider": "google",
        "free_tier": True,
        "models": ["gemini-1.5-flash"],
        "category": "text",
        "max_tokens": 8192,
        "cost": 0.0,  # Free tier
    },
}


class FreeIAOrchestrator:
    """Orquestrador que agrega IAs gratuitas e gerencia fallback chain."""

    def __init__(self):
        self.catalog: Dict[str, dict] = {}
        self.fallback_chain: List[str] = []
        self.active_provider: Optional[str] = None
        self.provider_status: Dict[str, dict] = {}
        self._init_time = time.time()

        self._load_config()
        self._build_fallback_chain()

        print(f"🆓 Free IA Orchestrator VMP-AI inicializado")
        print(f"   📦 Catalog: {len(self.catalog)} provedores")
        print(f"   🔄 Fallback chain: {len(self.fallback_chain)} stages")

    def _load_config(self):
        """Carrega configurações de IAs gratuitas."""
        if IA_CONFIG.exists():
            import yaml

            with open(IA_CONFIG) as f:
                user_config = yaml.safe_load(f)
            # Merge with defaults
            for key, provider in IA_CATALOG.items():
                if key in user_config:
                    provider.update(user_config[key])
            print(f"   ⚙️ Config IAs gratuitas carregadas de {IA_CONFIG}")
        else:
            print(f"   ⚠️ {IA_CONFIG} não encontrado,IA_CATALOG")

    def _build_fallback_chain(self):
        """Constrói a cadeia de fallback baseada em disponibilidade."""
        self.fallback_chain = []

        # Priority order: local first (no cost, no API key needed), then free tiers
        priority_order = [
            "ollama_local",
            "lm_studio_local",
            "openrouter_free",
            "anthropic_claude",
            "google_gemini",
        ]

        for key in priority_order:
            if key in IA_CATALOG:
                provider_config = IA_CATALOG[key]
                # Check if requirements are met
                if self._check_requirements(provider_config):
                    self.fallback_chain.append(key)
                    print(f"   🔗 Fallback stage: {provider_config['name']}")
                else:
                    print(
                        f"   ⏳ {provider_config['name']}: requirements not met (will be skipped in fallback)"
                    )

        if not self.fallback_chain:
            print("   ⚠️ Nenhuma IA gratuita disponível - check dependencies")

    def _check_requirements(self, provider: dict) -> bool:
        """Verifica se os requisitos de um provedor são atendidos."""
        requirements = provider.get("require", [])
        for req in requirements:
            if req == "ollama_running":
                # Check if ollama is available
                import subprocess

                try:
                    result = subprocess.run(
                        ["ollama", "list"], capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0:
                        return True
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    pass
            elif req == "lm_studio_running":
                # Check LM Studio
                import httpx

                try:
                    resp = httpx.get("http://127.0.0.1:1234/v1/models", timeout=3)
                    if resp.status_code == 200:
                        return True
                except Exception:
                    pass
        # If no specific checks fail, assume available
        return True

    async def get_best_ia(
        self,
        task_type: str = "general",
        max_tokens: int = None,
        preferences: dict = None,
    ) -> Optional[dict]:
        """Retorna a melhor IA disponível para o tipo de tarefa."""

        # Filter catalog by task type and capabilities
        candidates = []

        for key, provider in IA_CATALOG.items():
            # Skip if not in fallback chain but check availability
            if not self._check_requirements(provider):
                continue

            # Match category if specified
            if task_type and "category" in provider:
                if (
                    provider["category"] != task_type
                    and task_type not in provider["category"]
                ):
                    continue

            # Check token capacity
            tokens = max_tokens or provider.get("max_tokens", 4096)
            if tokens > provider.get("max_tokens", 4096):
                continue

            candidates.append((key, provider))

        if not candidates:
            return None

        # Select best: local first, then free tier quality
        # Priority: ollama_local > lm_studio > openrouter_free > anthropic > google
        priority = {
            "ollama_local": 1,
            "lm_studio_local": 2,
            "openrouter_free": 3,
            "anthropic_claude": 4,
            "google_gemini": 5,
        }

        candidates.sort(key=lambda x: priority.get(x[0], 99))

        selected = candidates[0]
        self.active_provider = selected[0]

        return {
            "provider": selected[0],
            "model": selected[1].get("models", ["unknown"])[0],
            "name": selected[1]["name"],
            "category": selected[1].get("category", "general"),
            "max_tokens": selected[1].get("max_tokens", 4096),
            "cost": selected[1].get("cost", 0.0),
            "fallback_chain": self.fallback_chain,
        }

    async def get_fallback_chain(self) -> List[dict]:
        """Retorna a cadeia completa de fallback como lista de opções."""
        chain = []
        for key in self.fallback_chain:
            if key in IA_CATALOG:
                provider = IA_CATALOG[key]
                chain.append(
                    {
                        "provider": key,
                        "name": provider["name"],
                        "models": provider.get("models", []),
                        "category": provider.get("category", "general"),
                        "cost": provider.get("cost", 0.0),
                    }
                )
        return chain

    def get_catalog(self) -> dict:
        """Retorna o catálogo completo."""
        return dict(IA_CATALOG)

    def status(self) -> dict:
        """Retorna status do orquestrador."""
        return {
            "active_provider": self.active_provider,
            "fallback_chain": self.fallback_chain,
            "catalog_size": len(self.catalog),
            "uptime": time.time() - self._init_time,
            "provider_status": self.provider_status,
        }


# CLI entry point
async def main():
    """CLI para o orquestrador de IAs."""
    orchestrator = FreeIAOrchestrator()

    print("""
╔════════════════════════════════════════════════════════════════╗
║               VMP-AI Free IA Orchestrator                     ║
║         Free-tier Aggregator with Smart Fallback              ║
╚════════════════════════════════════════════════════════════════╝
    """)

    while True:
        try:
            print("\n1. Melhor IA para tarefa")
            print("2. Cadeia de fallback")
            print("3. Catálogo completo")
            print("4. Status")
            print("5. Sair")

            choice = input("\nOpção: ").strip()

            if choice == "1":
                task_type = (
                    input(
                        "Tipo de tarefa (general/code/vision, Enter=general): "
                    ).strip()
                    or "general"
                )
                max_tokens = input("Max tokens (Enter=auto): ").strip()
                max_tokens = int(max_tokens) if max_tokens else None

                result = await orchestrator.get_best_ia(task_type, max_tokens)
                if result:
                    print(f"\n🆓 Melhor IA: {result['name']}")
                    print(f"   Provedor: {result['provider']}")
                    print(f"   Modelo: {result['model']}")
                    print(f"   Categoria: {result['category']}")
                    print(f"   Tokens: {result['max_tokens']}")
                    print(f"   Custo: R$ {result['cost']}")
                else:
                    print("❌ Nenhuma IA disponível para este tipo de tarefa")

            elif choice == "2":
                chain = await orchestrator.get_fallback_chain()
                print(f"\n🔄 Cadeia de Fallback ({len(chain)} stages):")
                for i, stage in enumerate(chain, 1):
                    print(
                        f"   {i}. {stage['name']} - {', '.join(stage['models'][:2])}..."
                    )

            elif choice == "3":
                catalog = orchestrator.get_catalog()
                print(f"\n📚 Catálogo de IAs Gratuitas ({len(catalog)} provedores):")
                for key, provider in catalog.items():
                    models_preview = ", ".join(provider.get("models", [])[:3])
                    print(f"   🆚 {provider['name']}")
                    print(
                        f"      Models: {models_preview}{'...' if len(provider.get('models', [])) > 3 else ''}"
                    )
                    print(f"      Categoria: {provider.get('category', 'general')}")
                    print(f"      Custo: R$ {provider.get('cost', 0.0)}")
                    print()

            elif choice == "4":
                status = orchestrator.status()
                print(f"\n📊 Status do Orchestrator:")
                print(f"   Ativo: {status['active_provider'] or 'nenhum'}")
                print(f"   Chain: {status['fallback_chain']}")
                print(f"   Uptime: {status['uptime']:.1f}s")

            elif choice == "5":
                break
            else:
                print("Opção inválida")

        except KeyboardInterrupt:
            print("\n👋 Encerrando.")
            break
        except Exception as e:
            print(f"❌ Erro: {e}")
            import traceback

            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

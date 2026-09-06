#!/usr/bin/env python3
"""VMP-AI Dynamic API Generator - Gera OpenAPI a partir de habilidades e deployed."""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

VMP_HOME = Path(os.getenv("VMP_HOME", str(Path.home() / ".vmp-ai")))
APIS_DIR = VMP_HOME / "apis"
APIS_REGISTRY = APIS_DIR / "registry.json"
DEPLOYED_DIR = APIS_DIR / "deployed"


class OpenAPIGenerator:
    """Gera especificações OpenAPI 3.1 a partir de habilidades VMP-AI."""

    def __init__(self):
        self.ensure_dirs()
        self.registry = self._load_registry()
        print("🔌 OpenAPI Generator VMP-AI inicializado")

    def ensure_dirs(self):
        """Cria diretórios necessários."""
        APIS_DIR.mkdir(parents=True, exist_ok=True)
        DEPLOYED_DIR.mkdir(parents=True, exist_ok=True)
        APIS_REGISTRY.touch(exist_ok=True)

    def _load_registry(self) -> dict:
        """Carrega o registry de APIs."""
        if APIS_REGISTRY.exists():
            import json
            with open(APIS_REGISTRY) as f:
                return json.load(f)
        return {"apis": [], "count": 0}

    def _save_registry(self):
        """Salva o registry."""
        with open(APIS_REGISTRY, "w") as f:
            json.dump(self.registry, f, indent=2, ensure_ascii=False)

    def generate_from_skill(self, skill_name: str, skill_def: dict, task_context: dict = None) -> dict:
        """Gera especificação OpenAPI a partir de uma skill definition."""
        
        # Analyze skill to extract API characteristics
        endpoints = self._extract_endpoints(skill_def, task_context)
        info = self._generate_info(skill_name, task_context)
        
        # Build OpenAPI 3.1 spec
        spec = {
            "openapi": "3.1.0",
            "info": info,
            "paths": endpoints,
            "components": {
                "schemas": self._generate_schemas(skill_def),
                "securitySchemes": {
                    "apiKey": {
                        "type": "apiKey",
                        "in": "header",
                        "name": "X-API-Key"
                    }
                }
            },
            "tags": self._generate_tags(skill_name),
            "servers": [{"url": "/", "description": "VMP-AI Dynamic API Server"}]
        }
        
        return spec

    def _generate_info(self, skill_name: str, context: dict) -> dict:
        """Gera info section do OpenAPI."""
        base_title = skill_name.replace("_", " ").title()
        version = context.get("version", "1.0.0") if context else "1.0.0"
        
        return {
            "title": f"VMP-AI {base_title} API",
            "version": version,
            "description": f"API dynamically generated from skill: {skill_name}"
        }

    def _extract_endpoints(self, skill_def: dict, context: dict) -> dict:
        """Extrai endpoints da skill definition."""
        paths = {}
        
        # Analyze skill for action types
        actions = skill_def.get("actions", [])
        if not actions:
            # Single endpoint placeholder
            paths["/"] = {
                "get": {
                    "summary": f"Execute {skill_name}",
                    "responses": {
                        "200": {"description": "Result of skill execution"},
                        "400": {"description": "Bad request or skill not found"}
                    }
                }
            }
            return paths
        
        for action in actions:
            method = action.get("method", "get").lower()
            path = action.get("path", "/")
            summary = action.get("summary", f"{skill_name} endpoint")
            
            if path not in paths:
                paths[path] = {}
            
            paths[path][method] = {
                "summary": summary,
                "responses": {
                    "200": {"description": "Success", "content": {
                        "application/json": {
                            "example": action.get("response_example", {"result": "ok"})
                        }
                    }},
                    "400": {"description": "Bad request"},
                    "500": {"description": "Internal error"}
                }
            }
        
        return paths

    def _generate_schemas(self, skill_def: dict) -> dict:
        """Gera schemas/components."""
        schemas = {}
        
        # Generate basic response schema
        schemas["SkillResponse"] = {
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "result": {"type": "any"},
                "data": {"type": "object", "description": "Skill output data"},
                "error": {"type": "string", "description": "Error message if any"}
            },
            "required": ["success"]
        }
        
        return schemas

    def _generate_tags(self, skill_name: str) -> list:
        """Gera tags para a API."""
        return [skill_name.replace("_", " ").title()[:50]]

    def register_api(self, skill_name: str, spec: dict, metadata: dict = None) -> str:
        """Registra uma API gerada no sistema."""
        api_id = str(uuid.uuid4())
        
        registration = {
            "api_id": api_id,
            "skill_name": skill_name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "spec": spec,
            "metadata": metadata or {}
        }
        
        self.registry["apis"].append(registration)
        self._save_registry()
        
        # Also save to deployed dir
        deployed_path = DEPLOYED_DIR / f"{api_id}.json"
        with open(deployed_path, "w") as f:
            json.dump(spec, f, indent=2, ensure_ascii=False)
        
        print(f"   📡 API registrada: {api_id} (skill: {skill_name})")
        return api_id

    def list_apis(self) -> list:
        """Lista APIs registradas."""
        return self.registry.get("apis", [])

    def get_api(self, api_id: str) -> Optional[dict]:
        """Retorna API pelo ID."""
        for api in self.registry.get("apis", []):
            if api.get("api_id") == api_id:
                return api
        return None


class APIDeployer:
    """Deploys generated APIs to various targets."""
    
    def __init__(self):
        self.deploy_targets = {
            "local": self._deploy_local,
            "fastapi": self._deploy_fastapi,
            "flask": self._deploy_flask,
        }
    
    def deploy(self, api_id: str, target: str = "local") -> dict:
        """Deploya uma API registrada."""
        api = self._get_api(api_id)
        if not api:
            return {"status": "error", "message": "API não encontrada"}
        
        deploy_fn = self.deploy_targets.get(target)
        if not deploy_fn:
            return {"status": "error", "message": f"Target '{target}' não suportado"}
        
        return deploy_fn(api)
    
    def _get_api(self, api_id: str) -> Optional[dict]:
        """Get API from registry."""
        # Try registry
        from .generator import OpenAPIGenerator
        gen = OpenAPIGenerator()
        return gen.get_api(api_id)
    
    def _deploy_local(self, api: dict) -> dict:
        """Deploya API localmente (server Python simples)."""
        api_id = api.get("api_id", "unknown")
        spec = api.get("spec", {})
        
        # Generate server code
        server_code = f'''
#!/usr/bin/env python3
"""Auto-generated VMP-AI API Server."""
import uvicorn
from fastapi import FastAPI

app = FastAPI(title="{spec.get('info', {}).get('title', 'VMP-AI API')}")

{self._generate_fastapi_routes(spec)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
'''
        
        server_path = DEPLOYED_DIR / f"server_{api_id}.py"
        with open(server_path, "w") as f:
            f.write(server_code)
        
        return {
            "status": "deployed_local",
            "message": f"API {api_id} deployada localmente em http://0.0.0.0:8000",
            "server_path": str(server_path)
        }
    
    def _generate_fastapi_routes(self, spec: dict) -> str:
        """Gera rotas FastAPI a partir do spec OpenAPI."""
        paths = spec.get("paths", {})
        routes = ""
        
        for path, methods in paths.items():
            for method, details in methods.items():
                if method in ["get", "post", "put", "delete"]:
                    route_name = details.get("summary", "endpoint")
                    routes += f'''
@app.{method}("{path}")
async def {route_name.replace("/", "_").replace("-", "_"): 
    return {{"status": "ok", "path": "{path}", "method": "{method}"}}'''
        
        return routes
    
    def _deploy_flask(self, api: dict) -> dict:
        """Deploya API Flask."""
        return {
            "status": "deploy_info",
            "message": "Deploy Flask não implementado nesta versão - use FastAPI local"
        }


# CLI entry point
async def main():
    """CLI para o gerador de APIs."""
    generator = OpenAPIGenerator()
    deployer = APIDeployer()
    
    print("""
╔════════════════════════════════════════════════════════════════╗
║                 VMP-AI Dynamic API Generator                  ║
║         Generate & Deploy OpenAPI 3.1 Specs                   ║
╚════════════════════════════════════════════════════════════════╝
    """)
    
    while True:
        try:
            print("\n1. Gerar API de skill")
            print("2. Listar APIs registradas")
            print("3. Deploy API")
            print("4. Sair")
            
            choice = input("\nOpção: ").strip()
            
            if choice == "1":
                skill_name = input("Nome da skill: ").strip()
                # Load skill def (simplified)
                task_ctx = {"version": "1.0.0"}
                spec = generator.generate_from_skill(skill_name, {}, task_ctx)
                api_id = generator.register_api(skill_name, spec, {"generated": True})
                print(f"✅ API gerada: {api_id}")
                print(f"📄 OpenAPI 3.1 specs geradas")
                
            elif choice == "2":
                apis = generator.list_apis()
                print(f"\n📋 APIs registradas ({len(apis)}):")
                for api in apis:
                    print(f"   - {api.get('api_id', 'N/A')[:8]}... {api.get('skill_name', 'N/A')}")
                    
            elif choice == "3":
                api_id = input("API ID para deploy: ").strip()
                target = input("Target (local/fastapi/flask, default local): ").strip() or "local"
                result = deployer.deploy(api_id, target)
                print(f"🚀 {result.get('message', 'Status desconhecido')}")
                
            elif choice == "4":
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
#!/usr/bin/env python3
"""VMP-AI Screen-Reading System - Integração browser_vision + OCR + Análise."""

import asyncio
import json
import os
import base64
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

# Try to import vision/OCR modules
try:
    import cv2

    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    from PIL import Image

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

VMP_HOME = Path(os.getenv("VMP_HOME", str(Path.home() / ".vmp-ai")))
SCREEN_DIR = VMP_HOME / "screen"


class ScreenAnalysisResult:
    """Resultado da análise de tela."""

    def __init__(self):
        self.objects: List[dict] = []
        self.text: List[str] = []
        self.buttons: List[dict] = []
        self.forms: List[dict] = []
        self.intent: Optional[str] = None
        self.confidence: float = 0.0
        raw_data: dict = {}

    def to_dict(self) -> dict:
        return {
            "objects": self.objects,
            "text": self.text,
            "buttons": self.buttons,
            "forms": self.forms,
            "intent": self.intent,
            "confidence": self.confidence,
        }


class ScreenReader:
    """Sistema completo de screen-reading para VMP-AI."""

    def __init__(self):
        self.capabilities: Dict[str, bool] = {
            "opencv": CV2_AVAILABLE,
            "pillow": PIL_AVAILABLE,
            "tesseract": self._check_tesseract(),
        }
        self.history: List[ScreenAnalysisResult] = []

        print(f"👁️ Screen-Reader VMP-AI inicializado")
        print(
            f"   📦 Capabilities: { {k: v for k, v in self.capabilities.items() if v} }"
        )

    def _check_tesseract(self) -> bool:
        """Verifica se tesseract está disponível."""
        import shutil

        return shutil.which("tesseract") is not None

    async def analyze_surface(
        self, image_data: bytes, source: str = "unknown"
    ) -> ScreenAnalysisResult:
        """Analisa uma superfície de tela e retorna resultado estruturado."""
        result = ScreenAnalysisResult()
        result.raw_data = {"source": source, "image_size": len(image_data)}

        if not image_data:
            result.confidence = 0.0
            return result

        # Step 1: OCR - Extrair texto
        if self.capabilities["pillow"] or self.capabilities["opencv"]:
            extracted_text = await self._extract_text_opencv(image_data)
            result.text = extracted_text if extracted_text else []
            result.confidence = max(result.confidence, 0.7 if extracted_text else 0.3)

        # Step 2: Detectar objetos/elementos UI
        if self.capabilities["opencv"]:
            ui_elements = await self._detect_ui_elements(image_data)
            result.objects = ui_elements["objects"]
            result.buttons = ui_elements["buttons"]
            result.forms = ui_elements["forms"]
            result.confidence = max(
                result.confidence, ui_elements.get("confidence", 0.5)
            )

        # Step 3: Inferir intenção
        result.intent = await self._infer_intent(result)
        if result.intent:
            result.confidence = max(result.confidence, 0.6)

        # Add to history
        self.history.append(result)
        if len(self.history) > 50:
            self.history = self.history[-50:]

        return result

    async def _extract_text_opencv(self, image_data: bytes) -> List[str]:
        """Extrai texto usando OpenCV + Tesseract."""
        if not CV2_AVAILABLE or not PIL_AVAILABLE:
            return []

        try:
            import numpy as np
            from PIL import Image

            # Decode image
            nparr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if img is None:
                return []

            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # Apply OCR using pytesseract (if available)
            try:
                import pytesseract

                text = pytesseract.image_to_string(gray, lang="eng")
                if text.strip():
                    return [text.strip()]
            except ImportError:
                pass

            # Fallback: simple extraction
            return []
        except Exception as e:
            print(f"   ⚠️ Erro na extração de texto: {e}")
            return []

    async def _detect_ui_elements(self, image_data: bytes) -> dict:
        """Detecta elementos UI na imagem."""
        result = {"objects": [], "buttons": [], "forms": [], "confidence": 0.5}

        if not CV2_AVAILABLE:
            return result

        try:
            import numpy as np

            nparr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if img is None:
                return result

            h, w = img.shape[:2]

            # Simple color-based detection (placeholder)
            # In production, would use a trained model for UI element detection

            # Detect bright buttons (approximate)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)

            # Find contours (potential buttons)
            contours, _ = cv2.findContours(
                thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )

            for cnt in contours[:20]:  # Limit to 20
                area = cv2.contourArea(cnt)
                if area > 500:  # Minimum size
                    x, y, cw, ch = cv2.boundingRect(cnt)
                    result["objects"].append(
                        {
                            "type": "potential_ui_element",
                            "x": x,
                            "y": y,
                            "w": cw,
                            "h": ch,
                            "area": area,
                            "center": (x + cw // 2, y + ch // 2),
                        }
                    )

                    # Heuristic: if aspect ratio is button-like
                    aspect_ratio = cw / ch if ch > 0 else 0
                    if 0.5 < aspect_ratio < 3.0:
                        result["buttons"].append(
                            {
                                "x": x,
                                "y": y,
                                "w": cw,
                                "h": ch,
                                "label": "button",
                                "confidence": min(area / 5000, 1.0),
                            }
                        )

            if result["objects"]:
                result["confidence"] = 0.8

        except Exception as e:
            print(f"   ⚠️ Erro na detecção de UI: {e}")

        return result

    async def _infer_intent(self, result: ScreenAnalysisResult) -> Optional[str]:
        """Inferir intenção a partir dos elementos detectados."""
        text_lower = " ".join(result.text).lower()
        obj_types = [o.get("type", "").lower() for o in result.objects]

        # Heuristic intent inference
        if any(k in text_lower for k in ["login", "sign in", "entrar"]):
            return "authentication"
        elif any(k in text_lower for k in ["search", "buscar", "find"]):
            return "search"
        elif any(k in text_lower for k in ["submit", "enviar", "send"]):
            return "form_submission"
        elif any(k in text_lower for k in ["new", "create", "novo"]):
            return "creation"
        elif any(k in text_lower for k in ["settings", "configurações"]):
            return "configuration"
        else:
            # Based on button types and positions
            if result.buttons:
                return "interaction"
            return None

    async def process_screenshot(self, screenshot_path: str) -> ScreenAnalysisResult:
        """Processa um arquivo de screenshot."""
        if not os.path.exists(screenshot_path):
            raise FileNotFoundError(f"Screenshot não encontrado: {screenshot_path}")

        with open(screenshot_path, "rb") as f:
            image_data = f.read()

        return await self.analyze_surface(image_data, source=screenshot_path)

    def get_capabilities(self) -> dict:
        """Retorna capacidades disponíveis."""
        return {
            "opencv": self.capabilities["opencv"],
            "pillow": self.capabilities["pillow"],
            "tesseract": self.capabilities["tesseract"],
            "history_size": len(self.history),
        }


# CLI entry point
async def main():
    """CLI para testar o screen-reader."""
    reader = ScreenReader()

    print("""
╔════════════════════════════════════════════════════════════════╗
║               VMP-AI Screen-Reading System                    ║
║         browser_vision + OCR + UI Element Detection           ║
╚════════════════════════════════════════════════════════════════╝
    """)

    while True:
        try:
            path = input("\n📸 Caminho do screenshot (ou 'quit'): ").strip()
            if path.lower() in ["quit", "exit", "q"]:
                break

            if not path:
                continue

            result = await reader.process_screenshot(path)
            print(f"\n📊 Análise de Tela:")
            print(f"   ✍️ Texto: {result.text[:3] if result.text else 'nenhum'}")
            print(f"   🎯 Elementos: {len(result.objects)} objetos")
            print(f"   🔘 Botões: {len(result.buttons)} botões")
            print(f"   🎯 Intenção: {result.intent or 'nenhuma'}")
            print(f"   📊 Confiança: {result.confidence:.2f}")
            print(f"   ⚙️ Capacidades: {reader.get_capabilities()}")

        except FileNotFoundError as e:
            print(f"❌ {e}")
        except Exception as e:
            print(f"❌ Erro: {e}")
            import traceback

            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

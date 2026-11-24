#!/usr/bin/env python3
"""Check the local Aiko installation without creating or changing user data."""

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)


def section(title: str) -> None:
    print(f"\n{'=' * 58}\n {title}\n{'=' * 58}")


def check_python() -> bool:
    ok = sys.version_info >= (3, 11)
    print(f"{'✅' if ok else '❌'} Python {sys.version_info.major}.{sys.version_info.minor} (requiere 3.11+)")
    return ok


def check_dependencies() -> bool:
    required = ["fastapi", "uvicorn", "langchain", "langgraph", "chromadb", "sqlalchemy", "pydantic", "jose", "dotenv"]
    missing = []
    for package in required:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    print("✅ Dependencias base instaladas" if not missing else f"❌ Faltan: {', '.join(missing)}")
    return not missing


def check_structure() -> bool:
    required = [
        "main.py", "requirements.txt", ".env.example", "README.md",
        "api/auth.py", "api/routes/auth.py", "api/routes/chat.py",
        "config/settings.py", "agent/core.py", "memory/manager.py",
    ]
    missing = [name for name in required if not (ROOT / name).is_file()]
    print("✅ Archivos principales presentes" if not missing else f"❌ Faltan: {', '.join(missing)}")
    return not missing


def check_private_config() -> bool:
    try:
        from dotenv import dotenv_values
        values = dotenv_values(ROOT / ".env")
    except Exception:
        values = {}
    username = values.get("AUTH_USERNAME") or os.getenv("AUTH_USERNAME")
    password = values.get("AUTH_PASSWORD") or os.getenv("AUTH_PASSWORD")
    jwt_secret = values.get("JWT_SECRET") or os.getenv("JWT_SECRET")
    ok = bool(username and password and jwt_secret and len(jwt_secret) >= 32)
    print("✅ Credenciales privadas configuradas" if ok else "❌ Configura AUTH_USERNAME, AUTH_PASSWORD y JWT_SECRET (32+ caracteres) en .env")
    return ok


def check_selected_provider() -> bool:
    try:
        from dotenv import dotenv_values
        values = dotenv_values(ROOT / ".env")
    except Exception:
        values = {}
    provider = (values.get("LLM_PROVIDER") or os.getenv("LLM_PROVIDER") or "ollama").lower()
    if provider == "ollama":
        try:
            import requests
            base = values.get("OLLAMA_BASE_URL") or os.getenv("OLLAMA_BASE_URL") or "http://127.0.0.1:11434"
            model = values.get("OLLAMA_MODEL") or os.getenv("OLLAMA_MODEL") or "qwen2.5:7b"
            response = requests.get(f"{base.rstrip('/')}/api/tags", timeout=3)
            names = {item.get("name") for item in response.json().get("models", [])}
            ok = response.ok and model in names
        except Exception:
            ok = False
        print("✅ Ollama y el modelo configurado están disponibles" if ok else "❌ Ollama no responde o falta el modelo configurado")
        return ok
    key_name = {"google": "GOOGLE_API_KEY", "groq": "GROQ_API_KEY"}.get(provider)
    key = (values.get(key_name) or os.getenv(key_name)) if key_name else None
    ok = bool(key)
    print(f"{'✅' if ok else '❌'} Proveedor seleccionado: {provider}" + (" (clave configurada)" if ok else " (falta configurar su clave)"))
    return ok


def check_api() -> bool:
    try:
        import requests
        port = os.getenv("PORT", "8000")
        response = requests.get(f"http://127.0.0.1:{port}/api/ready", timeout=4)
        ok = response.ok and response.json().get("ready") is True
    except Exception:
        ok = False
    print("✅ API lista" if ok else "⚠️ API todavía no está lista o alguna comprobación de /api/ready falló")
    return ok


def main() -> int:
    section("Verificación de Aiko")
    checks = [
        ("Python", check_python),
        ("Dependencias", check_dependencies),
        ("Estructura", check_structure),
        ("Autenticación privada", check_private_config),
        ("Proveedor IA", check_selected_provider),
        ("API", check_api),
    ]
    results = [(name, fn()) for name, fn in checks]
    section("Resultado")
    for name, ok in results:
        print(f"{'✅' if ok else '❌'} {name}")
    return 0 if all(ok for _, ok in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python
"""
Installation verification script for Aiko Backend
Run this to verify your installation is complete and working
"""

import sys
import subprocess
import os
from pathlib import Path


def print_section(title):
    """Print a section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def check_python():
    """Check Python version."""
    print("🐍 Checking Python version...")
    version = sys.version_info
    print(f"   Python {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 11):
        print("   ❌ Python 3.11+ required")
        return False
    
    print("   ✅ Python version OK")
    return True


def check_dependencies():
    """Check if required packages are installed."""
    print("\n📦 Checking installed packages...")
    
    required = [
        "fastapi",
        "uvicorn",
        "langchain",
        "langgraph",
        "chromadb",
        "sqlalchemy",
        "pydantic",
    ]
    
    missing = []
    for package in required:
        try:
            __import__(package.replace("-", "_"))
            print(f"   ✅ {package}")
        except ImportError:
            print(f"   ❌ {package} - MISSING")
            missing.append(package)
    
    if missing:
        print(f"\n   ⚠️  Missing packages: {', '.join(missing)}")
        print("   Run: pip install -r requirements.txt")
        return False
    
    return True


def check_structure():
    """Check if all required directories and files exist."""
    print("\n📁 Checking project structure...")
    
    required_files = [
        "main.py",
        "requirements.txt",
        ".env.template",
        "README.md",
        "config/settings.py",
        "agent/core.py",
        "memory/manager.py",
        "tools/search.py",
        "voice/manager.py",
        "api/auth.py",
        "api/routes/chat.py",
    ]
    
    missing = []
    for file_path in required_files:
        if Path(file_path).exists():
            print(f"   ✅ {file_path}")
        else:
            print(f"   ❌ {file_path} - MISSING")
            missing.append(file_path)
    
    if missing:
        print(f"\n   ⚠️  Missing files: {', '.join(missing)}")
        return False
    
    return True


def check_env_file():
    """Check if .env file exists."""
    print("\n⚙️  Checking configuration...")
    
    if Path(".env").exists():
        print("   ✅ .env file found")
        return True
    elif Path(".env.template").exists():
        print("   ⚠️  .env file not found (template exists)")
        print("   Run: cp .env.template .env")
        return False
    else:
        print("   ❌ No .env or .env.template found")
        return False


def check_directories():
    """Check if required data directories exist."""
    print("\n📂 Checking data directories...")
    
    dirs = [
        "data",
        "data/chroma",
        "data/uploads",
        "data/documents",
    ]
    
    missing = []
    for dir_path in dirs:
        if Path(dir_path).exists():
            print(f"   ✅ {dir_path}")
        else:
            print(f"   ⚠️  {dir_path} (will be created on first run)")
            missing.append(dir_path)
    
    if missing:
        print(f"\n   Creating missing directories...")
        for dir_path in missing:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
            print(f"   ✅ Created {dir_path}")
    
    return True


def check_ollama():
    """Check if Ollama is running."""
    print("\n🔌 Checking Ollama connection...")
    
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        
        if response.status_code == 200:
            print("   ✅ Ollama is running")
            data = response.json()
            models = data.get("models", [])
            if models:
                print(f"   📦 Available models: {len(models)}")
                for model in models[:3]:
                    print(f"      - {model.get('name', 'unknown')}")
            else:
                print("   ⚠️  No models installed")
                print("   Run: ollama pull mistral")
            return True
        else:
            print("   ❌ Ollama is not responding correctly")
            return False
    except requests.exceptions.ConnectionError:
        print("   ⚠️  Ollama is not running")
        print("   Start it with: ollama serve")
        return False
    except Exception as e:
        print(f"   ❌ Error checking Ollama: {e}")
        return False


def check_api_health():
    """Check if FastAPI is running."""
    print("\n🏥 Checking API health...")
    
    try:
        import requests
        response = requests.get("http://localhost:8000/api/health", timeout=2)
        
        if response.status_code == 200:
            print("   ✅ API is running and healthy")
            data = response.json()
            print(f"   App: {data.get('app', 'unknown')}")
            print(f"   Version: {data.get('version', 'unknown')}")
            return True
        else:
            print(f"   ❌ API returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("   ⚠️  API is not running")
        print("   Start it with: python main.py")
        return False
    except Exception as e:
        print(f"   ❌ Error checking API: {e}")
        return False


def main():
    """Run all checks."""
    print_section("Aiko Backend Installation Verification")
    
    checks = [
        ("Python Version", check_python),
        ("Dependencies", check_dependencies),
        ("Project Structure", check_structure),
        ("Environment File", check_env_file),
        ("Data Directories", check_directories),
        ("Ollama Connection", check_ollama),
        ("API Health", check_api_health),
    ]
    
    results = {}
    critical_failed = False
    
    for check_name, check_func in checks:
        try:
            results[check_name] = check_func()
        except Exception as e:
            print(f"   ❌ Error: {e}")
            results[check_name] = False
            critical_failed = True
    
    # Summary
    print_section("Summary")
    
    for check_name, passed in results.items():
        status = "✅" if passed else "❌"
        print(f"{status} {check_name}")
    
    passed_count = sum(1 for v in results.values() if v)
    total_count = len(results)
    
    print(f"\n{passed_count}/{total_count} checks passed\n")
    
    if critical_failed or passed_count < total_count:
        print("⚠️  Some checks failed. Please review the output above.")
        print("\nCommon fixes:")
        print("  • pip install -r requirements.txt")
        print("  • cp .env.template .env")
        print("  • mkdir -p data/{chroma,uploads,documents}")
        print("  • ollama serve  (in another terminal)")
        print("  • python main.py  (start the backend)\n")
        return 1
    else:
        print("✅ All checks passed! Aiko Backend is ready to use.")
        print("\nNext steps:")
        print("  1. Connect your frontend to http://localhost:8000")
        print("  2. View API docs at http://localhost:8000/docs")
        print("  3. Check README.md for detailed documentation\n")
        return 0


if __name__ == "__main__":
    sys.exit(main())

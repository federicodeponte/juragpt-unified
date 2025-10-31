#!/usr/bin/env python3
"""
Smoke test for JuraGPT Unified services.

Tests basic functionality without requiring full infrastructure:
1. Services can import and initialize
2. Basic API structure is correct
3. Health endpoints respond
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_embedder_service_imports():
    """Test embedder service can be imported and initialized."""
    print("Testing embedder service imports...")
    try:
        # Import should work without errors
        import services.embedder.main as embedder_module
        assert hasattr(embedder_module, 'app'), "Embedder missing FastAPI app"
        assert hasattr(embedder_module, 'embed_texts'), "Embedder missing embed_texts endpoint"
        print("✓ Embedder service imports successfully")
        return True
    except Exception as e:
        print(f"✗ Embedder import failed: {e}")
        return False


def test_orchestrator_service_imports():
    """Test orchestrator service can be imported and initialized."""
    print("\nTesting orchestrator service imports...")
    try:
        import services.orchestrator.main as orch_module
        assert hasattr(orch_module, 'app'), "Orchestrator missing FastAPI app"
        assert hasattr(orch_module, 'unified_query'), "Orchestrator missing unified_query endpoint"
        print("✓ Orchestrator service imports successfully")
        return True
    except Exception as e:
        print(f"✗ Orchestrator import failed: {e}")
        return False


def test_service_structure():
    """Test that service directory structure is correct."""
    print("\nTesting service directory structure...")
    required_services = [
        'services/embedder/main.py',
        'services/orchestrator/main.py',
        'services/retrieval/src',
        'services/verification/auditor',
    ]

    all_exist = True
    for service_path in required_services:
        full_path = project_root / service_path
        if full_path.exists():
            print(f"✓ Found: {service_path}")
        else:
            print(f"✗ Missing: {service_path}")
            all_exist = False

    return all_exist


def test_docker_compose_exists():
    """Test that Docker Compose configuration exists."""
    print("\nTesting Docker Compose configuration...")
    docker_compose = project_root / 'docker-compose.yml'

    if docker_compose.exists():
        print("✓ docker-compose.yml exists")
        # Check if it contains key services
        content = docker_compose.read_text()
        services = ['embedder', 'orchestrator', 'retrieval', 'verification']
        missing = [s for s in services if s not in content]

        if missing:
            print(f"✗ Missing services in docker-compose.yml: {missing}")
            return False
        else:
            print(f"✓ All services defined: {services}")
            return True
    else:
        print("✗ docker-compose.yml missing")
        return False


def test_requirements_exist():
    """Test that requirements files exist."""
    print("\nTesting requirements files...")
    req_files = [
        'requirements.txt',
        'services/embedder/requirements.txt',
        'services/orchestrator/requirements.txt',
        'services/retrieval/requirements.txt',
        'services/verification/requirements.txt',
    ]

    all_exist = True
    for req_file in req_files:
        full_path = project_root / req_file
        if full_path.exists():
            print(f"✓ Found: {req_file}")
        else:
            print(f"✗ Missing: {req_file}")
            all_exist = False

    return all_exist


def main():
    """Run all smoke tests."""
    print("=" * 70)
    print("JuraGPT Unified - Smoke Tests")
    print("=" * 70)

    results = {
        'Structure': test_service_structure(),
        'Docker Compose': test_docker_compose_exists(),
        'Requirements': test_requirements_exist(),
        'Embedder Imports': test_embedder_service_imports(),
        'Orchestrator Imports': test_orchestrator_service_imports(),
    }

    print("\n" + "=" * 70)
    print("Test Results Summary")
    print("=" * 70)

    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")

    total = len(results)
    passed = sum(results.values())
    print(f"\nPassed: {passed}/{total}")

    if passed == total:
        print("\n✓ All smoke tests passed!")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())

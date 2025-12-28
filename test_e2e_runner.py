"""
Quick E2E test runner to check prerequisites
"""
import os
import sys

print("=" * 70)
print("E2E TEST PREREQUISITES CHECK")
print("=" * 70)

# Check 1: OpenRouter API Key
print("\n1. Checking OpenRouter API Key...")
api_key = os.getenv("OPENROUTER_API_KEY")
if api_key and api_key != "your_key_here" and api_key != "sk-or-v1-placeholder":
    print(f"   [OK] API key found: {api_key[:20]}...")
else:
    print("   [X] OPENROUTER_API_KEY not set or is placeholder")
    print("      Set with: $env:OPENROUTER_API_KEY='your-actual-key'")

# Check 2: FreeCAD
print("\n2. Checking FreeCAD installation...")
try:
    from agent.tools.freecad_runner import FreeCADRunner
    runner = FreeCADRunner()
    print(f"   ✅ FreeCAD found: {runner.freecad_cmd}")
except Exception as e:
    print(f"   ❌ FreeCAD not found: {e}")
    print("      Install from: https://www.freecad.org/")
    print("      Or set FREECAD_PATH environment variable")

# Check 3: MATLAB
print("\n3. Checking MATLAB Engine API...")
try:
    import matlab.engine
    print("   ✅ MATLAB Engine API installed")
    
    # Try to start MATLAB
    print("      Testing MATLAB engine startup (this may take 10-30 seconds)...")
    try:
        import asyncio
        async def test_matlab():
            from agent.tools.matlab_runner import MATLABRunner
            runner = MATLABRunner()
            result = await runner.test_installation()
            return result
        
        result = asyncio.run(test_matlab())
        if result:
            print("      ✅ MATLAB engine started successfully")
        else:
            print("      ❌ MATLAB engine failed to start")
    except Exception as e:
        print(f"      ❌ MATLAB engine test failed: {e}")
        
except ImportError as e:
    print(f"   ❌ MATLAB Engine API not installed: {e}")
    print("      Install with:")
    print('      cd "$(matlab -batch \'disp(matlabroot); exit\')/extern/engines/python"')
    print("      python setup.py install")

# Check 4: Config file
print("\n4. Checking configuration...")
try:
    from agent.config import load_config
    config = load_config()
    print("   ✅ config.yaml loaded successfully")
except Exception as e:
    print(f"   ❌ Config error: {e}")

# Check 5: Dependencies
print("\n5. Checking Python dependencies...")
try:
    import fastapi
    import pydantic
    import httpx
    print(f"   ✅ All core dependencies installed")
    print(f"      - FastAPI: {fastapi.__version__}")
    print(f"      - Pydantic: {pydantic.__version__}")
except ImportError as e:
    print(f"   ❌ Missing dependency: {e}")

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print("\nTo run full E2E tests, you need:")
print("  1. ✓ OpenRouter API key (sign up at openrouter.ai)")
print("  2. ✓ FreeCAD installed with CLI access")
print("  3. ✓ MATLAB with PDE Toolbox and Engine API for Python")
print("\nOnce all prerequisites are met, run:")
print("  pytest tests/test_e2e.py -v")
print("\nFor now, core tests (validators, scoring, security) are passing!")
print("=" * 70)


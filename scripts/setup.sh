#!/bin/bash
# Setup script for CAD-MATLAB Agent

set -e

echo "=== CAD-MATLAB Agent Setup ==="
echo ""

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $python_version"

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."
if command -v poetry &> /dev/null; then
    echo "Using Poetry..."
    poetry install
else
    echo "Using pip..."
    pip install -r requirements.txt
fi

# Check FreeCAD
echo ""
echo "Checking FreeCAD installation..."
if command -v freecadcmd &> /dev/null; then
    echo "✓ FreeCAD CLI found: $(which freecadcmd)"
    freecadcmd --version
else
    echo "✗ FreeCAD CLI not found in PATH"
    echo "  Please install FreeCAD and set FREECAD_PATH in .env"
fi

# Check MATLAB
echo ""
echo "Checking MATLAB installation..."
if command -v matlab &> /dev/null; then
    echo "✓ MATLAB found: $(which matlab)"
    
    echo ""
    echo "IMPORTANT: Install MATLAB Engine API for Python:"
    echo "  cd \"\$(matlab -batch 'disp(matlabroot); exit')/extern/engines/python\""
    echo "  python setup.py install"
else
    echo "✗ MATLAB not found in PATH"
    echo "  Please install MATLAB and add to PATH"
fi

# Create .env file
echo ""
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "✓ .env created"
    echo "  Please edit .env and add your OPENROUTER_API_KEY"
else
    echo "✓ .env already exists"
fi

# Create runs directory
mkdir -p runs
echo "✓ Created runs directory"

# Initialize database
echo ""
echo "Initializing database..."
python -c "
import asyncio
from agent.db.models import init_db
from agent.config import load_config

async def main():
    config = load_config()
    await init_db(config.storage.database_url)
    print('✓ Database initialized')

asyncio.run(main())
"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit .env and add OPENROUTER_API_KEY"
echo "  2. Install MATLAB Engine API (see above)"
echo "  3. Run: python -m agent.api.main (or: uvicorn agent.api.main:app --reload)"
echo ""


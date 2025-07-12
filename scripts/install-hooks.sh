#!/bin/bash

# Script to install git hooks for the MCP Studio project

set -e

echo "🔧 Installing git hooks..."

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Create hooks directory if it doesn't exist
mkdir -p "$PROJECT_ROOT/.git/hooks"

# Install the pre-commit hook
if [ -f "$PROJECT_ROOT/.git/hooks/pre-commit" ]; then
    echo "📋 Pre-commit hook already exists. Backing up and updating..."
    cp "$PROJECT_ROOT/.git/hooks/pre-commit" "$PROJECT_ROOT/.git/hooks/pre-commit.backup"
else
    echo "📋 Installing pre-commit hook..."
fi

# Create the pre-commit hook content
cat > "$PROJECT_ROOT/.git/hooks/pre-commit" << 'EOF'
#!/bin/bash

# Pre-commit hook: Run full test suite before allowing commits
# This ensures all commits maintain code quality and test coverage

set -e

echo "🔒 Pre-commit hook: Running safety checks..."
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get project root
PROJECT_ROOT="$(git rev-parse --show-toplevel)"
cd "$PROJECT_ROOT"

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if Docker services are running
echo "🐳 Checking Docker services..."
if ! docker-compose ps | grep -q "Up"; then
    print_error "Docker services are not running!"
    echo "Please start services with: docker-compose up -d"
    exit 1
fi
print_status "Docker services are running"

# Give services a moment if they just started
sleep 2

# Check service connectivity
echo "🌐 Checking service connectivity..."
if ! curl -s http://localhost:8080/health >/dev/null 2>&1; then
    print_error "Gateway service not responding!"
    echo "Check service status with: docker-compose ps"
    exit 1
fi
print_status "Services are accessible"

# Run the full test suite
echo "🧪 Running comprehensive test suite..."
echo "This ensures all commits maintain safety and quality standards."
echo ""

cd tests
if uv run pytest --tb=short -q; then
    print_status "All tests passed! ✨"
    echo ""
    print_status "Commit approved - code quality maintained"
else
    print_error "Tests failed! Commit blocked for safety."
    echo ""
    echo "💡 To fix:"
    echo "   1. Review test failures above"
    echo "   2. Fix issues and stage changes with: git add ."
    echo "   3. Try committing again"
    echo ""
    echo "🚨 To bypass (NOT RECOMMENDED): git commit --no-verify"
    exit 1
fi

echo ""
echo "🔒 Safety first: All quality checks passed!"
EOF

chmod +x "$PROJECT_ROOT/.git/hooks/pre-commit"

echo "✅ Git hooks installed successfully!"
echo ""
echo "The pre-commit hook will now run the complete test suite before each commit."
echo "This ensures safety-first development with automatic quality validation."
echo ""
echo "To skip the hook (not recommended): git commit --no-verify" 
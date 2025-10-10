#!/bin/bash

# FastAPI Test Runner Script
# This script runs comprehensive tests for both API and NetworkXMCP services

set -e  # Exit on any error

echo "🧪 FastAPI Test Suite Runner"
echo "============================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running in Docker
if [ -f /.dockerenv ]; then
    print_status "Running in Docker environment"
    IN_DOCKER=true
else
    print_status "Running in host environment"
    IN_DOCKER=false
fi

# Function to run tests with coverage
run_tests() {
    local service=$1
    local path=$2
    
    print_status "Running tests for $service..."
    
    cd "$path"
    
    # Install test dependencies if not in Docker
    if [ "$IN_DOCKER" = false ]; then
        print_status "Installing test dependencies for $service..."
        if [ -f "pyproject.toml" ]; then
            pip install -e ".[test]"
        else
            print_warning "No pyproject.toml found in $path"
        fi
    fi
    
    # Run pytest with coverage
    if pytest --version > /dev/null 2>&1; then
        print_status "Executing pytest for $service..."
        pytest -v \
            --cov=. \
            --cov-report=term-missing \
            --cov-report=html:htmlcov \
            --cov-report=xml \
            --junit-xml=test-results.xml
        
        if [ $? -eq 0 ]; then
            print_success "$service tests completed successfully"
        else
            print_error "$service tests failed"
            return 1
        fi
    else
        print_error "pytest not found. Please install test dependencies."
        return 1
    fi
    
    cd - > /dev/null
}

# Function to run integration tests
run_integration_tests() {
    print_status "Running integration tests..."
    
    # Start services if not already running
    if [ "$IN_DOCKER" = false ]; then
        print_status "Starting services with Docker Compose..."
        docker compose up -d
        sleep 10  # Wait for services to start
    fi
    
    cd API
    
    # Run integration tests specifically
    if pytest test_integration.py -v; then
        print_success "Integration tests completed successfully"
    else
        print_error "Integration tests failed"
        return 1
    fi
    
    cd - > /dev/null
}

# Function to generate coverage report
generate_coverage_report() {
    print_status "Generating combined coverage report..."
    
    # Combine coverage data if multiple .coverage files exist
    if command -v coverage > /dev/null 2>&1; then
        coverage combine API/.coverage NetworkXMCP/.coverage 2>/dev/null || true
        coverage report --show-missing
        coverage html -d combined_htmlcov
        print_success "Combined coverage report generated in combined_htmlcov/"
    else
        print_warning "Coverage command not found. Individual reports available in each service directory."
    fi
}

# Main execution
main() {
    print_status "Starting FastAPI test suite execution..."
    
    # Check if we're in the correct directory
    if [ ! -f "docker-compose.yml" ]; then
        print_error "docker-compose.yml not found. Please run this script from the project root."
        exit 1
    fi
    
    # Parse command line arguments
    SKIP_API=false
    SKIP_NETWORKXMCP=false
    SKIP_INTEGRATION=false
    VERBOSE=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-api)
                SKIP_API=true
                shift
                ;;
            --skip-networkxmcp)
                SKIP_NETWORKXMCP=true
                shift
                ;;
            --skip-integration)
                SKIP_INTEGRATION=true
                shift
                ;;
            --verbose)
                VERBOSE=true
                shift
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo "Options:"
                echo "  --skip-api           Skip API tests"
                echo "  --skip-networkxmcp   Skip NetworkXMCP tests"
                echo "  --skip-integration   Skip integration tests"
                echo "  --verbose            Enable verbose output"
                echo "  --help               Show this help message"
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done
    
    # Track overall success
    OVERALL_SUCCESS=true
    
    # Run API tests
    if [ "$SKIP_API" = false ]; then
        if ! run_tests "API" "API"; then
            OVERALL_SUCCESS=false
        fi
    else
        print_warning "Skipping API tests"
    fi
    
    # Run NetworkXMCP tests
    if [ "$SKIP_NETWORKXMCP" = false ]; then
        if ! run_tests "NetworkXMCP" "NetworkXMCP"; then
            OVERALL_SUCCESS=false
        fi
    else
        print_warning "Skipping NetworkXMCP tests"
    fi
    
    # Run integration tests
    if [ "$SKIP_INTEGRATION" = false ]; then
        if ! run_integration_tests; then
            OVERALL_SUCCESS=false
        fi
    else
        print_warning "Skipping integration tests"
    fi
    
    # Generate coverage report
    generate_coverage_report
    
    # Final status
    echo ""
    echo "============================="
    if [ "$OVERALL_SUCCESS" = true ]; then
        print_success "All tests completed successfully! 🎉"
        exit 0
    else
        print_error "Some tests failed. Check the output above for details."
        exit 1
    fi
}

# Run main function with all arguments
main "$@"
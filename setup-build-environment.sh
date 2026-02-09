#!/bin/bash
set -euo pipefail

################################################################################
# ytdl-sub Docker Build Environment Setup Script
#
# This script prepares a machine running podman to build the ytdl-sub headless
# Docker image. It handles Python environment setup, dependency installation,
# and podman configuration.
#
# Usage:
#   ./setup-build-environment.sh [--skip-podman-check] [--use-docker]
#
# Options:
#   --skip-podman-check  Skip podman configuration checks
#   --use-docker         Use docker instead of podman
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USE_DOCKER=false
SKIP_PODMAN_CHECK=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-podman-check)
            SKIP_PODMAN_CHECK=true
            shift
            ;;
        --use-docker)
            USE_DOCKER=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [--skip-podman-check] [--use-docker]"
            echo ""
            echo "Options:"
            echo "  --skip-podman-check  Skip podman configuration checks"
            echo "  --use-docker         Use docker instead of podman"
            echo "  -h, --help           Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

################################################################################
# Color output functions
################################################################################

if [[ -t 1 ]]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    NC='\033[0m' # No Color
else
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    NC=''
fi

log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

################################################################################
# Check prerequisites
################################################################################

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check Python 3
    if ! command -v python3 &> /dev/null; then
        log_error "python3 is not installed"
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 --version | awk '{print $2}')
    log_success "Python ${PYTHON_VERSION} found"
    
    # Check container runtime
    if [[ "$USE_DOCKER" == "true" ]]; then
        if ! command -v docker &> /dev/null; then
            log_error "docker is not installed"
            exit 1
        fi
        CONTAINER_CMD="docker"
        log_success "Docker found"
    else
        if ! command -v podman &> /dev/null; then
            log_error "podman is not installed"
            log_info "Install podman with: sudo pacman -S podman (Arch) or sudo apt install podman (Debian/Ubuntu)"
            exit 1
        fi
        CONTAINER_CMD="podman"
        log_success "Podman found"
    fi
    
    # Check git
    if ! command -v git &> /dev/null; then
        log_warn "git is not installed - version tagging may not work"
    else
        log_success "Git found"
    fi
}

################################################################################
# Setup podman for rootless operation
################################################################################

setup_podman_rootless() {
    if [[ "$USE_DOCKER" == "true" ]] || [[ "$SKIP_PODMAN_CHECK" == "true" ]]; then
        return 0
    fi
    
    log_info "Checking podman rootless configuration..."
    
    # Check if podman can run rootless
    if ! podman info &> /dev/null; then
        log_warn "Podman cannot run in rootless mode yet"
        log_info "Setting up podman for rootless operation..."
        
        # Check for subuid/subgid
        if ! grep -q "^$(whoami):" /etc/subuid 2>/dev/null; then
            log_error "No subuid mapping found for user $(whoami)"
            log_info "Run as root: echo '$(whoami):100000:65536' >> /etc/subuid"
            log_info "Run as root: echo '$(whoami):100000:65536' >> /etc/subgid"
            exit 1
        fi
        
        # Initialize podman
        log_info "Initializing podman..."
        if ! podman system migrate; then
            log_error "Failed to initialize podman"
            exit 1
        fi
    fi
    
    # Test podman
    if podman info > /dev/null 2>&1; then
        log_success "Podman is configured for rootless operation"
    else
        log_error "Podman is not working correctly"
        log_info "Try running: podman system reset"
        exit 1
    fi
}

################################################################################
# Setup Python virtual environment
################################################################################

setup_python_venv() {
    log_info "Setting up Python virtual environment..."
    
    cd "$SCRIPT_DIR"
    
    # Check for uv
    if command -v uv &> /dev/null; then
        log_success "uv found, using it for faster operations"
        
        # Create venv with uv
        if [[ ! -d .venv ]]; then
            log_info "Creating virtual environment with uv..."
            uv venv .venv
        else
            log_info "Virtual environment already exists"
        fi
        
        # Activate and install dependencies
        log_info "Installing build dependencies..."
        source .venv/bin/activate
        uv pip install build
        
        # Create pip/pip3 wrappers for Makefile compatibility
        log_info "Creating pip wrappers for Makefile compatibility..."
        cat > .venv/bin/pip << 'EOF'
#!/bin/bash
exec uv pip "$@"
EOF
        chmod +x .venv/bin/pip
        ln -sf pip .venv/bin/pip3
        
    else
        log_warn "uv not found, falling back to standard venv"
        log_info "For faster builds, install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
        
        # Create standard venv
        if [[ ! -d .venv ]]; then
            log_info "Creating virtual environment..."
            python3 -m venv .venv
        else
            log_info "Virtual environment already exists"
        fi
        
        # Activate and install dependencies
        source .venv/bin/activate
        log_info "Installing build dependencies..."
        pip install --upgrade pip
        pip install build
    fi
    
    log_success "Python virtual environment ready"
}

################################################################################
# Build Python wheel
################################################################################

build_wheel() {
    log_info "Building Python wheel package..."
    
    cd "$SCRIPT_DIR"
    source .venv/bin/activate
    
    # Clean previous builds
    log_info "Cleaning previous builds..."
    make clean
    
    # Build wheel
    log_info "Building wheel (this may take a few minutes)..."
    if make wheel; then
        log_success "Python wheel built successfully"
        
        # Show wheel info
        WHEEL_FILE=$(ls -1 dist/*.whl 2>/dev/null | head -1)
        if [[ -n "$WHEEL_FILE" ]]; then
            log_info "Wheel file: $WHEEL_FILE"
        fi
    else
        log_error "Failed to build Python wheel"
        exit 1
    fi
}

################################################################################
# Stage Docker files
################################################################################

stage_docker_files() {
    log_info "Staging files for Docker build..."
    
    cd "$SCRIPT_DIR"
    source .venv/bin/activate
    
    if make docker_stage; then
        log_success "Docker files staged successfully"
        
        # Verify staged files
        if [[ -f docker/root/*.whl ]]; then
            log_info "Wheel file staged in docker/root/"
        fi
        
        if [[ -d docker/root/defaults/examples ]]; then
            log_info "Example files staged in docker/root/defaults/"
        fi
    else
        log_error "Failed to stage Docker files"
        exit 1
    fi
}

################################################################################
# Build Docker image
################################################################################

build_docker_image() {
    log_info "Building Docker image with ${CONTAINER_CMD}..."
    
    cd "$SCRIPT_DIR"
    
    # Determine if we need sudo
    SUDO_CMD=""
    if [[ "$USE_DOCKER" == "true" ]]; then
        # Check if docker needs sudo
        if ! docker info &> /dev/null; then
            if sudo docker info &> /dev/null; then
                SUDO_CMD="sudo"
                log_warn "Docker requires sudo access"
            else
                log_error "Cannot run docker (even with sudo)"
                exit 1
            fi
        fi
    fi
    
    # Build the image
    log_info "Building ytdl-sub:local image (this will take several minutes)..."
    if $SUDO_CMD $CONTAINER_CMD build --progress=plain --no-cache -t ytdl-sub:local docker/; then
        log_success "Docker image built successfully!"
        
        # Show image info
        log_info "Image details:"
        $SUDO_CMD $CONTAINER_CMD images ytdl-sub:local
        
    else
        log_error "Failed to build Docker image"
        exit 1
    fi
}

################################################################################
# Test Docker image
################################################################################

test_docker_image() {
    log_info "Testing Docker image..."
    
    SUDO_CMD=""
    if [[ "$USE_DOCKER" == "true" ]] && ! docker info &> /dev/null; then
        SUDO_CMD="sudo"
    fi
    
    # Test running the image
    if $SUDO_CMD $CONTAINER_CMD run --rm ytdl-sub:local ytdl-sub -h > /dev/null 2>&1; then
        log_success "Docker image test passed!"
        
        # Show version
        VERSION=$($SUDO_CMD $CONTAINER_CMD run --rm ytdl-sub:local ytdl-sub --version 2>&1 | head -1)
        log_info "ytdl-sub version: $VERSION"
    else
        log_warn "Docker image test failed (image may still be functional)"
    fi
}

################################################################################
# Main execution
################################################################################

main() {
    echo ""
    log_info "ytdl-sub Docker Build Environment Setup"
    log_info "========================================"
    echo ""
    
    check_prerequisites
    setup_podman_rootless
    setup_python_venv
    build_wheel
    stage_docker_files
    build_docker_image
    test_docker_image
    
    echo ""
    log_success "==================================================="
    log_success "Build complete! Image tagged as: ytdl-sub:local"
    log_success "==================================================="
    echo ""
    log_info "Next steps:"
    log_info "  1. Run the container:"
    log_info "     ${CONTAINER_CMD} run --rm -v /path/to/config:/config ytdl-sub:local ytdl-sub -h"
    echo ""
    log_info "  2. Tag and push to registry (optional):"
    log_info "     ${CONTAINER_CMD} tag ytdl-sub:local your-registry/ytdl-sub:latest"
    log_info "     ${CONTAINER_CMD} push your-registry/ytdl-sub:latest"
    echo ""
    log_info "  3. Build other variants:"
    log_info "     make docker_ubuntu  # Ubuntu-based image"
    log_info "     make docker_gui     # GUI-enabled image"
    echo ""
}

# Run main function
main

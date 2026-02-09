# Docker Build Environment Setup

This document explains how to set up a machine to build the ytdl-sub headless Docker image using Podman or Docker.

## Quick Start

```bash
# Run the automated setup script
./setup-build-environment.sh
```

The script will:
1. Check for required dependencies
2. Configure Podman for rootless operation
3. Set up Python virtual environment
4. Build the Python wheel package
5. Stage Docker build files
6. Build the Docker image
7. Test the built image

## Prerequisites

### Required
- **Python 3.10+**: For building the wheel package
- **Podman or Docker**: For building container images
- **Git**: For version tagging (optional but recommended)

### Arch Linux
```bash
sudo pacman -S python podman git
```

### Debian/Ubuntu
```bash
sudo apt update
sudo apt install python3 python3-venv podman git
```

### Fedora/RHEL
```bash
sudo dnf install python3 podman git
```

## Podman Rootless Setup

If you're using Podman for the first time, you may need to configure it for rootless operation:

### 1. Configure subuid/subgid mappings

Check if mappings exist:
```bash
grep "^$(whoami):" /etc/subuid /etc/subgid
```

If not found, add them (requires root):
```bash
sudo usermod --add-subuids 100000-165535 --add-subgids 100000-165535 $(whoami)
# OR manually:
echo "$(whoami):100000:65536" | sudo tee -a /etc/subuid
echo "$(whoami):100000:65536" | sudo tee -a /etc/subgid
```

### 2. Initialize Podman
```bash
podman system migrate
```

### 3. Verify Podman works
```bash
podman info
```

## Python Environment Options

### Option 1: Using uv (Recommended - Faster)

Install uv:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

The setup script will automatically detect and use uv for faster operations.

### Option 2: Standard venv

The script falls back to standard Python venv if uv is not available.

## Manual Build Process

If you prefer to build manually instead of using the setup script:

### 1. Setup Python Environment

```bash
# With uv (faster)
uv venv .venv
source .venv/bin/activate
uv pip install build

# Create pip3 wrapper for Makefile
cat > .venv/bin/pip << 'EOF'
#!/bin/bash
exec uv pip "$@"
EOF
chmod +x .venv/bin/pip
ln -sf pip .venv/bin/pip3

# OR with standard venv
python3 -m venv .venv
source .venv/bin/activate
pip install build
```

### 2. Build Python Wheel

```bash
source .venv/bin/activate
make clean
make wheel
```

### 3. Stage Docker Files

```bash
make docker_stage
```

### 4. Build Docker Image

```bash
# With Podman (rootless)
podman build --progress=plain --no-cache -t ytdl-sub:local docker/

# With Docker (may require sudo)
docker build --progress=plain --no-cache -t ytdl-sub:local docker/
# OR
sudo docker build --progress=plain --no-cache -t ytdl-sub:local docker/
```

## Script Options

```bash
# Use Docker instead of Podman
./setup-build-environment.sh --use-docker

# Skip Podman configuration checks
./setup-build-environment.sh --skip-podman-check

# Show help
./setup-build-environment.sh --help
```

## Building Other Image Variants

After setting up the environment, you can build other variants:

### Ubuntu-based Image
```bash
source .venv/bin/activate
make docker_ubuntu
```

### GUI-enabled Image
```bash
source .venv/bin/activate
make docker_gui
```

## Troubleshooting

### Podman: "permission denied"

**Problem**: Podman gives permission denied errors.

**Solutions**:
1. Ensure subuid/subgid mappings are configured (see Podman Rootless Setup above)
2. Run `podman system migrate` to initialize
3. Check SELinux is not blocking: `sudo setenforce 0` (temporary)
4. Reset Podman: `podman system reset` (warning: removes all containers/images)

### Python: "pip3: command not found"

**Problem**: The Makefile can't find pip3.

**Solution**: The setup script creates pip3 wrappers automatically. If building manually, ensure you've created the wrapper scripts (see Manual Build Process above).

### Build: "externally-managed-environment"

**Problem**: System Python won't allow package installation.

**Solution**: Use the virtual environment created by the setup script:
```bash
source .venv/bin/activate
```

### Docker: "Cannot connect to the Docker daemon"

**Problem**: Docker requires root/sudo access.

**Solution**: Run with sudo or use Podman instead:
```bash
./setup-build-environment.sh --use-docker
# OR add your user to docker group:
sudo usermod -aG docker $(whoami)
# Then log out and back in
```

### Build fails with "No space left on device"

**Problem**: Insufficient disk space for build.

**Solution**:
1. Clean up old containers/images: `podman system prune -a`
2. Clean Python build artifacts: `make clean`
3. Free up disk space

## Testing the Built Image

```bash
# Show help
podman run --rm ytdl-sub:local ytdl-sub -h

# Show version
podman run --rm ytdl-sub:local ytdl-sub --version

# Run with mounted config
podman run --rm -v ./config:/config ytdl-sub:local ytdl-sub sub subscriptions.yaml
```

## CI/CD Integration

For automated builds in CI/CD pipelines:

```bash
#!/bin/bash
set -euxo pipefail

# Install dependencies
apt-get update && apt-get install -y python3 python3-venv podman

# Run setup script
./setup-build-environment.sh --skip-podman-check

# Tag and push
podman tag ytdl-sub:local registry.example.com/ytdl-sub:${CI_COMMIT_TAG}
podman push registry.example.com/ytdl-sub:${CI_COMMIT_TAG}
```

## Advanced Configuration

### Custom Image Tags

```bash
# Build with custom tag
podman build -t my-registry/ytdl-sub:v1.0.0 docker/
```

### Multi-architecture Builds

```bash
# Build for multiple architectures
podman build --platform linux/amd64,linux/arm64 -t ytdl-sub:local docker/
```

### Build Arguments

The Dockerfile supports standard build arguments:
```bash
podman build --build-arg HTTP_PROXY=http://proxy:8080 -t ytdl-sub:local docker/
```

## Contributing

If you encounter issues with the setup script or have improvements:

1. Check existing issues on GitHub
2. Provide detailed error messages and system information
3. Test your fix on a clean system
4. Submit a pull request with documentation updates

## Additional Resources

- [Podman Documentation](https://docs.podman.io/)
- [Python venv Documentation](https://docs.python.org/3/library/venv.html)
- [uv Documentation](https://github.com/astral-sh/uv)
- [ytdl-sub Documentation](https://github.com/jmbannon/ytdl-sub)

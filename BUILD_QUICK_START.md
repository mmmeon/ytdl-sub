# Quick Start: Building ytdl-sub Docker Images

This guide gets you building Docker images quickly. For detailed information, see [BUILD_ENVIRONMENT.md](BUILD_ENVIRONMENT.md).

## TL;DR - One Command Build

```bash
./setup-build-environment.sh
```

This single command will:
- ✓ Check all prerequisites
- ✓ Setup Python environment
- ✓ Build the wheel package
- ✓ Build the Docker image
- ✓ Test the built image

## Alternative: Using Make

```bash
make -f Makefile.build docker
```

Or build all variants:
```bash
make -f Makefile.build all
```

## What You Need

**Required:**
- Python 3.10+ 
- Podman or Docker
- Git (for version tagging)

**Quick Install (Arch Linux):**
```bash
sudo pacman -S python podman git
```

## Common Issues & Fixes

### ❌ "permission denied" (Podman)

**Fix:** Configure rootless podman
```bash
echo "$(whoami):100000:65536" | sudo tee -a /etc/subuid
echo "$(whoami):100000:65536" | sudo tee -a /etc/subgid
podman system migrate
```

### ❌ "pip3: command not found"

**Fix:** The setup script handles this automatically. If running manually:
```bash
source .venv/bin/activate
```

### ❌ "Cannot connect to Docker daemon"

**Fix:** Either use podman:
```bash
./setup-build-environment.sh  # Uses podman by default
```

Or add yourself to docker group:
```bash
sudo usermod -aG docker $(whoami)
# Log out and back in
```

## Testing Your Build

```bash
# Show version
podman run --rm ytdl-sub:local ytdl-sub --version

# Show help
podman run --rm ytdl-sub:local ytdl-sub --help

# Run with config
podman run --rm -v ./config:/config ytdl-sub:local ytdl-sub view
```

## All Available Tools

### 1. Automated Setup Script
**Best for:** First-time setup, CI/CD
```bash
./setup-build-environment.sh [--use-docker] [--skip-podman-check]
```

### 2. Enhanced Makefile
**Best for:** Development workflow
```bash
make -f Makefile.build help        # Show all targets
make -f Makefile.build docker      # Build headless
make -f Makefile.build all         # Build all variants
make -f Makefile.build test-docker # Test the image
make -f Makefile.build quick-build # Fast rebuild
```

### 3. Docker Compose
**Best for:** Local testing
```bash
docker-compose -f docker-compose.build.yml build
docker-compose -f docker-compose.build.yml up test
```

### 4. Original Makefile
**Best for:** Manual control
```bash
source .venv/bin/activate
make docker       # Headless
make docker_ubuntu # Ubuntu variant
make docker_gui   # GUI variant
```

## CI/CD Integration

### GitHub Actions
Copy `.github/workflows/build-docker-example.yml` to your workflows directory.

### GitLab CI
Copy `.gitlab-ci-example.yml` to `.gitlab-ci.yml`

### Generic CI
```bash
#!/bin/bash
./setup-build-environment.sh
# Image is now built and tagged as ytdl-sub:local
```

## Project Structure

```
.
├── setup-build-environment.sh    # Main setup script
├── Makefile.build                # Enhanced build targets
├── docker-compose.build.yml      # Compose configuration
├── BUILD_ENVIRONMENT.md          # Detailed documentation
├── BUILD_QUICK_START.md          # This file
└── docker/
    ├── Dockerfile                # Headless image (Alpine)
    ├── Dockerfile.ubuntu         # Ubuntu-based image
    └── Dockerfile.gui            # GUI-enabled image
```

## Next Steps

1. **Build the image** (you are here!)
   ```bash
   ./setup-build-environment.sh
   ```

2. **Test locally**
   ```bash
   podman run --rm ytdl-sub:local ytdl-sub --version
   ```

3. **Deploy to registry** (optional)
   ```bash
   make -f Makefile.build tag REGISTRY=ghcr.io/yourusername
   make -f Makefile.build push REGISTRY=ghcr.io/yourusername
   ```

4. **Setup CI/CD** (optional)
   - Copy example workflow to `.github/workflows/` or `.gitlab-ci.yml`
   - Commit and push
   - Automated builds on every push/tag

## Getting Help

- **Detailed setup:** [BUILD_ENVIRONMENT.md](BUILD_ENVIRONMENT.md)
- **Script options:** `./setup-build-environment.sh --help`
- **Make targets:** `make -f Makefile.build help`
- **Troubleshooting:** See BUILD_ENVIRONMENT.md "Troubleshooting" section

## Examples

### Build specific variant
```bash
make -f Makefile.build build-ubuntu
make -f Makefile.build build-gui
```

### Development workflow
```bash
# Initial setup
./setup-build-environment.sh

# Make code changes...

# Quick rebuild (uses cache)
make -f Makefile.build quick-build

# Test
make -f Makefile.build test-docker

# Dev shell
make -f Makefile.build dev-shell
```

### Production build
```bash
# Clean build
make -f Makefile.build clean-all
make -f Makefile.build all

# Tag for production
make -f Makefile.build tag REGISTRY=registry.example.com IMAGE_TAG=v1.0.0

# Push
make -f Makefile.build push REGISTRY=registry.example.com IMAGE_TAG=v1.0.0
```

---

**Ready to build?** Run: `./setup-build-environment.sh`

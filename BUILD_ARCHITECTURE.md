# ytdl-sub Docker Build Architecture

This document provides a visual overview of the build system architecture and workflow.

## Build System Components

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Build System Overview                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────┐ │
│  │  setup-build-    │    │  Makefile.build  │    │  docker-     │ │
│  │  environment.sh  │◄───┤  (Enhanced)      │    │  compose     │ │
│  │  (Main Script)   │    │                  │    │              │ │
│  └────────┬─────────┘    └──────────────────┘    └──────────────┘ │
│           │                                                         │
│           ├──────────────┬──────────────┬──────────────────┐       │
│           ▼              ▼              ▼                  ▼       │
│  ┌─────────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ Check       │  │ Setup    │  │ Build    │  │ Build Docker  │  │
│  │ Dependencies│  │ Python   │  │ Wheel    │  │ Image         │  │
│  └─────────────┘  └──────────┘  └──────────┘  └───────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Build Workflow

### Option 1: Automated (Recommended)

```
┌──────────────────────────────────────────────────────────────┐
│ User runs: ./setup-build-environment.sh                      │
└─────────────────────┬────────────────────────────────────────┘
                      │
                      ▼
            ┌─────────────────────┐
            │ Check Prerequisites │
            │  - Python 3.10+     │
            │  - Podman/Docker    │
            │  - Git              │
            └──────────┬──────────┘
                      │
                      ▼
            ┌─────────────────────┐
            │ Setup Podman        │
            │  - Check rootless   │
            │  - Verify subuid    │
            │  - Test connection  │
            └──────────┬──────────┘
                      │
                      ▼
            ┌─────────────────────┐
            │ Create Python venv  │
            │  - Use uv (fast)    │
            │  - Or standard venv │
            │  - Install build    │
            └──────────┬──────────┘
                      │
                      ▼
            ┌─────────────────────┐
            │ Build Python Wheel  │
            │  - make clean       │
            │  - make wheel       │
            │  - Generate .whl    │
            └──────────┬──────────┘
                      │
                      ▼
            ┌─────────────────────┐
            │ Stage Docker Files  │
            │  - Copy wheel       │
            │  - Copy examples    │
            │  - make docker_stage│
            └──────────┬──────────┘
                      │
                      ▼
            ┌─────────────────────┐
            │ Build Docker Image  │
            │  - podman build     │
            │  - Tag as :local    │
            │  - Tag as :latest   │
            └──────────┬──────────┘
                      │
                      ▼
            ┌─────────────────────┐
            │ Test Built Image    │
            │  - Run --version    │
            │  - Run --help       │
            │  - Show image info  │
            └──────────┬──────────┘
                      │
                      ▼
            ┌─────────────────────┐
            │   Build Complete!   │
            │  ytdl-sub:local     │
            └─────────────────────┘
```

### Option 2: Enhanced Makefile

```
┌────────────────────────────────────────────────────┐
│ User runs: make -f Makefile.build docker          │
└────────────────────┬───────────────────────────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │ Check if .venv exists│
          └──────────┬───────────┘
                     │
          ┌──────────┴───────────┐
          │ No                   │ Yes
          ▼                      ▼
┌──────────────────┐   ┌──────────────────┐
│ Call setup target│   │ Skip to build    │
│ (runs script)    │   │ (use existing)   │
└────────┬─────────┘   └────────┬─────────┘
         │                      │
         └──────────┬───────────┘
                    ▼
        ┌────────────────────────┐
        │ Build Docker image     │
        │ (podman/docker build)  │
        └────────────────────────┘
```

## File Structure and Dependencies

```
ytdlsub/
│
├── src/                           # Python source code
│   └── ytdl_sub/
│
├── docker/                        # Docker build context
│   ├── Dockerfile                 # Alpine-based (headless)
│   ├── Dockerfile.ubuntu          # Ubuntu-based
│   ├── Dockerfile.gui             # GUI-enabled
│   └── root/                      # Staged files
│       ├── *.whl                  # Built wheel (staged)
│       └── defaults/
│           └── examples/          # Example configs (staged)
│
├── setup-build-environment.sh     # Main automation script
│   └── Calls ──────┐
│                   ▼
├── Makefile                       # Original build targets
│   ├── wheel ──────┐             # Build Python package
│   ├── docker_stage│             # Copy files to docker/root/
│   └── docker ─────┘             # Build image (needs sudo)
│
├── Makefile.build                 # Enhanced targets
│   ├── Uses setup-build-environment.sh
│   └── Wraps original Makefile
│
├── docker-compose.build.yml       # Compose orchestration
│   └── Defines multi-stage build
│
└── CI/CD Examples
    ├── .github/workflows/build-docker-example.yml
    └── .gitlab-ci-example.yml
```

## Python Environment Setup

```
┌─────────────────────────────────────────────────────────┐
│                  Python Environment                     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Check for uv ────┬──── Found ───┐                    │
│                   │               ▼                     │
│                   │      ┌─────────────────┐           │
│                   │      │ uv venv .venv   │           │
│                   │      │ uv pip install  │ (Fast)    │
│                   │      │ Create wrappers │           │
│                   │      └─────────────────┘           │
│                   │                                     │
│                   └──── Not Found ──┐                  │
│                                     ▼                   │
│                            ┌──────────────────┐         │
│                            │ python3 -m venv  │         │
│                            │ pip install      │ (Slower)│
│                            └──────────────────┘         │
│                                     │                   │
│                                     ▼                   │
│                          ┌──────────────────┐           │
│                          │ source .venv/bin/│           │
│                          │      activate    │           │
│                          └──────────────────┘           │
│                                     │                   │
│                                     ▼                   │
│                          ┌──────────────────┐           │
│                          │ make wheel       │           │
│                          │ make docker_stage│           │
│                          └──────────────────┘           │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## Container Runtime Decision Tree

```
                    ┌──────────────────┐
                    │ Which runtime?   │
                    └────────┬─────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
              ▼                             ▼
    ┌─────────────────┐           ┌─────────────────┐
    │   Use Podman    │           │   Use Docker    │
    │  (rootless)     │           │  (may need sudo)│
    └────────┬────────┘           └────────┬────────┘
             │                              │
             ▼                              ▼
    ┌─────────────────┐           ┌─────────────────┐
    │ Check subuid/   │           │ Check docker    │
    │ subgid mappings │           │ group membership│
    └────────┬────────┘           └────────┬────────┘
             │                              │
      ┌──────┴───────┐              ┌──────┴───────┐
      │ Not setup    │ Setup        │ Not member   │ Member
      ▼              ▼              ▼              ▼
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│  Error   │  │ podman   │  │  sudo    │  │  docker  │
│  Exit    │  │  build   │  │  docker  │  │  build   │
└──────────┘  └──────────┘  └──────────┘  └──────────┘
```

## CI/CD Pipeline Architecture

### GitHub Actions Flow

```
┌───────────────────────────────────────────────────────────┐
│                    GitHub Actions                         │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  Trigger: push/tag/PR                                    │
│           │                                               │
│           ▼                                               │
│  ┌────────────────────┐                                  │
│  │ Checkout code      │                                  │
│  └─────────┬──────────┘                                  │
│            ▼                                              │
│  ┌────────────────────┐                                  │
│  │ Setup Python 3.11  │                                  │
│  └─────────┬──────────┘                                  │
│            ▼                                              │
│  ┌────────────────────┐                                  │
│  │ Install uv         │                                  │
│  └─────────┬──────────┘                                  │
│            ▼                                              │
│  ┌────────────────────┐                                  │
│  │ Build wheel        │                                  │
│  └─────────┬──────────┘                                  │
│            ▼                                              │
│  ┌────────────────────┐                                  │
│  │ Setup Buildx       │                                  │
│  └─────────┬──────────┘                                  │
│            ▼                                              │
│  ┌────────────────────┐                                  │
│  │ Build multi-arch   │ (amd64, arm64)                  │
│  └─────────┬──────────┘                                  │
│            ▼                                              │
│  ┌────────────────────┐                                  │
│  │ Push to GHCR       │ (if not PR)                     │
│  └────────────────────┘                                  │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

### GitLab CI Flow

```
┌───────────────────────────────────────────────────────────┐
│                      GitLab CI                            │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  Stage: prepare                                           │
│  │  ┌──────────────────┐                                │
│  └─▶│ Build wheel      │───┐                            │
│     └──────────────────┘   │ Artifacts                  │
│                            │                             │
│  Stage: build              ▼                             │
│  │  ┌──────────────────┐ ┌─────────────────┐           │
│  ├─▶│ Headless (Alpine)│ │ ubuntu          │           │
│  │  └──────────────────┘ └─────────────────┘           │
│  │  ┌──────────────────┐                                │
│  └─▶│ GUI              │                                │
│     └──────────────────┘                                │
│                            │                             │
│  Stage: test               ▼                             │
│  │  ┌──────────────────┐ ┌─────────────────┐           │
│  ├─▶│ Functionality    │ │ Security (Trivy)│           │
│  │  └──────────────────┘ └─────────────────┘           │
│                            │                             │
│  Stage: push               ▼                             │
│  │  ┌──────────────────┐                                │
│  └─▶│ Push to registry │                                │
│     └──────────────────┘                                │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

## Image Variants

```
                    ┌──────────────────┐
                    │   ytdl-sub       │
                    │   Source Code    │
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
    ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
    │  Dockerfile │  │ Dockerfile  │  │ Dockerfile  │
    │  (headless) │  │   .ubuntu   │  │    .gui     │
    └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
           │                │                │
           ▼                ▼                ▼
    ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
    │  Alpine     │  │  Ubuntu     │  │  Alpine +   │
    │  3.19+      │  │  22.04      │  │  Desktop    │
    │             │  │             │  │             │
    │  Minimal    │  │  Standard   │  │  GUI apps   │
    │  ~200MB     │  │  ~500MB     │  │  ~800MB     │
    └─────────────┘  └─────────────┘  └─────────────┘
```

## Dependency Graph

```
┌─────────────────────────────────────────────────────────┐
│                Build Dependencies                        │
└─────────────────────────────────────────────────────────┘

  Python 3.10+
       │
       ├─── build (package)
       │     └─── setuptools
       │
       ├─── uv (optional, faster)
       │
       └─── ytdl-sub dependencies
             ├─── yt-dlp
             ├─── mutagen
             ├─── mergedeep
             └─── ... (see pyproject.toml)

  Container Runtime
       │
       ├─── Podman (recommended)
       │     ├─── subuid/subgid
       │     └─── rootless support
       │
       └─── Docker
             └─── docker group OR sudo

  Docker Image Runtime
       │
       ├─── Alpine packages
       │     ├─── python3 >= 3.10
       │     ├─── ffmpeg > 5.1
       │     ├─── aria2 >= 1.36.0
       │     ├─── deno
       │     └─── phantomjs (x86_64)
       │
       └─── Python packages
             ├─── ytdl-sub (wheel)
             ├─── curl-cffi
             └─── yt-dlp-ejs
```

## Quick Reference

### Build Methods Comparison

| Method | Best For | Setup Time | Flexibility | CI/CD Ready |
|--------|----------|------------|-------------|-------------|
| `setup-build-environment.sh` | First time | ~5 min | ⭐⭐⭐ | ✅ Yes |
| `make -f Makefile.build` | Development | ~2 min | ⭐⭐⭐⭐⭐ | ✅ Yes |
| `docker-compose` | Testing | ~3 min | ⭐⭐⭐ | ⚠️  Partial |
| Original `make docker` | Manual | ~5 min | ⭐⭐⭐⭐ | ⚠️  Partial |

### Troubleshooting Quick Links

- **Podman issues** → See BUILD_ENVIRONMENT.md "Podman Rootless Setup"
- **Python issues** → See BUILD_ENVIRONMENT.md "Python Environment Options"
- **Build failures** → See BUILD_ENVIRONMENT.md "Troubleshooting"
- **CI/CD** → See .github/workflows/ or .gitlab-ci-example.yml

---

*For detailed documentation, see [BUILD_ENVIRONMENT.md](BUILD_ENVIRONMENT.md)*  
*For quick start, see [BUILD_QUICK_START.md](BUILD_QUICK_START.md)*

---
name: environment-setup-analyzer
description: Strategic approach for setting up applications and development environments. Evaluates installation methods in order of reliability and simplicity. Use when installing applications, setting up dev environments, building from source, using Docker, package managers like Homebrew, apt, or deciding between installation approaches. Includes analysis of architecture compatibility, dependency management, and troubleshooting build failures.
---

# Environment Setup Analyzer

## Purpose

Provides a systematic strategy for evaluating and choosing the best method to set up applications and development environments. Based on real-world experience, prioritizes simplicity and reliability over complexity.

## When to Use

Activate this skill when:
- Setting up new applications or tools
- Installing development environments
- Choosing between Docker, native builds, or package managers
- Troubleshooting failed installations
- Deciding between multiple installation approaches
- Working with architecture compatibility issues (ARM64 vs x86_64)
- Building from source vs using pre-built binaries

## The Setup Decision Framework

### 1. Package Manager First (Fastest & Most Reliable)

**Always check native package managers first:**

#### macOS
```bash
# Search Homebrew
brew search <app-name>
brew info <app-name>
brew install <app-name>
brew install --cask <app-name>  # For GUI apps
```

#### Linux (Debian/Ubuntu)
```bash
apt search <app-name>
apt show <app-name>
sudo apt install <app-name>
```

#### Linux (RHEL/Fedora)
```bash
dnf search <app-name>
dnf info <app-name>
sudo dnf install <app-name>
```

**Why First:**
- ✅ Handles dependencies automatically
- ✅ Architecture compatibility managed
- ✅ Clean install/uninstall
- ✅ Automatic updates
- ✅ One command setup
- ✅ Battle-tested by community
- ✅ No build environment needed

**When to Use:**
- Established open-source projects
- Official distributions available
- Standard installations
- Production environments

### 2. Official Pre-built Binaries (Second Choice)

**Check project's releases page:**
- GitHub Releases
- Official download pages
- Distribution channels

**Verify:**
- ✅ Architecture match (ARM64 vs x86_64)
- ✅ OS compatibility
- ✅ Version requirements
- ✅ Dependency documentation

**Why Second:**
- Simple installation
- No build required
- Verified by maintainers
- Usually includes dependencies

**Considerations:**
- May need Rosetta 2 on Apple Silicon
- Manual updates required
- No dependency management
- May require additional setup

### 3. Docker/Containers (For Isolation)

**When Docker Makes Sense:**
- Multi-service applications
- Need environment isolation
- Complex dependency trees
- Development/testing environments
- Consistent environments across teams

**Architecture Considerations:**
```yaml
# Check image architecture
docker manifest inspect <image>

# Force platform
docker run --platform linux/amd64 <image>
```

**Watch Out For:**
- ❌ Architecture mismatches (x86_64 images on ARM64)
- ❌ GUI applications (limited support)
- ❌ System-level watchers (need host access)
- ❌ Performance overhead
- ❌ Additional complexity

**Best Practices:**
```yaml
# docker-compose.yml
version: '3.7'
services:
  app:
    platform: linux/arm64  # Specify architecture
    build:
      context: .
      dockerfile: Dockerfile
    restart: unless-stopped
    volumes:
      - ./data:/data  # Persistent data
```

### 4. Build from Source (Last Resort)

**Only when:**
- No package manager option
- Need latest unreleased features
- Custom compilation flags needed
- Contributing to the project

**Pre-Build Checklist:**
```bash
# Check language versions
python --version
node --version
cargo --version
go version

# Check for version conflicts
# Example: Python 3.14 too new for some packages
# Example: Node 18+ vs Node 16 requirements
```

**Common Pitfalls:**

1. **Python Version Conflicts**
   ```bash
   # Use virtual environment with correct Python version
   python3.11 -m venv venv
   source venv/bin/activate
   ```

2. **Rust/Cargo Dependencies**
   ```bash
   # Check Rust version requirements
   rustc --version
   # Update if needed
   rustup update
   ```

3. **Native Dependencies**
   ```bash
   # macOS
   brew install <native-deps>

   # Linux
   sudo apt install build-essential libssl-dev
   ```

4. **Architecture-Specific Builds**
   - Check if project supports your architecture
   - Look for ARM64/Apple Silicon notes
   - Consider using older stable releases

**Build Process:**
```bash
# 1. Clone repository
git clone <repo-url>
cd <repo>

# 2. Check documentation
cat README.md
cat INSTALL.md
cat CONTRIBUTING.md

# 3. Initialize submodules (if needed)
git submodule update --init --recursive

# 4. Create isolated environment
python -m venv venv  # or use Poetry
source venv/bin/activate

# 5. Install dependencies
make install  # or
poetry install  # or
npm install

# 6. Build
make build  # or
npm run build  # or
cargo build --release
```

## Real-World Example: ActivityWatch Setup

### What We Tried

1. **Docker Approach** ❌
   - Built Debian container with x86_64 binaries
   - Failed: Rosetta error on ARM64 macOS
   - Time wasted: 30+ minutes

2. **Build from Source** ❌
   - Created Python virtual environment
   - Installed with Poetry
   - Failed: Python 3.14 incompatible with PyO3 (max 3.13)
   - Time wasted: 20+ minutes

3. **Homebrew** ✅
   - One command: `brew install --cask activitywatch`
   - Success in 2 minutes
   - Automatic Rosetta 2 handling
   - Clean installation

### Lessons Learned

- Check package managers FIRST, not as afterthought
- Architecture matters (ARM64 vs x86_64)
- Bleeding-edge language versions cause issues
- Simplicity > complexity for standard installs
- Save complex approaches for when needed

## Decision Tree

```
Need to install application?
│
├─ Is it in package manager?
│  ├─ YES → Use package manager ✅
│  └─ NO → Continue
│
├─ Official pre-built binary available?
│  ├─ YES → Check architecture match
│  │  ├─ Match → Use binary ✅
│  │  └─ No match → Continue
│  └─ NO → Continue
│
├─ Need environment isolation?
│  ├─ YES → Consider Docker
│  │  └─ Check architecture support
│  └─ NO → Continue
│
└─ Must build from source
   ├─ Check language version compatibility
   ├─ Check native dependencies
   ├─ Use virtual environment
   └─ Follow project's build docs
```

## Troubleshooting Common Issues

### Architecture Mismatch

**Symptom:** `exec format error`, `rosetta error`, `cannot execute binary`

**Solution:**
```bash
# Check your architecture
uname -m
# arm64 = Apple Silicon
# x86_64 = Intel

# Check binary architecture
file /path/to/binary

# macOS: Install Rosetta 2 if needed
softwareupdate --install-rosetta --agree-to-license
```

### Dependency Version Conflicts

**Symptom:** `version not supported`, `requires Python <=3.13`, `incompatible with`

**Solution:**
```bash
# Use version managers
pyenv install 3.11.0
pyenv local 3.11.0

# Or use containers with correct versions
docker run -it python:3.11 bash
```

### Missing Native Dependencies

**Symptom:** `cannot find -lssl`, `library not found`

**Solution:**
```bash
# macOS
brew install openssl libffi

# Linux
sudo apt install build-essential pkg-config libssl-dev
```

### Build Hangs or Times Out

**Symptom:** Build stops responding, excessive memory use

**Solution:**
```bash
# Limit parallel jobs
make -j2  # Instead of -j$(nproc)

# Increase timeout
cargo build --release  # Can take 10+ minutes

# Check disk space
df -h
```

## Quick Reference Commands

### Check System Info
```bash
# Architecture
uname -m

# OS version
sw_vers  # macOS
lsb_release -a  # Linux

# Language versions
python --version
node --version
cargo --version
go version
```

### Package Manager Searches
```bash
# Homebrew
brew search <term>
brew info <package>

# apt
apt search <term>
apt show <package>

# dnf
dnf search <term>
dnf info <package>
```

### Docker Platform Info
```bash
# Check image platforms
docker manifest inspect <image>

# Run with specific platform
docker run --platform linux/amd64 <image>
docker run --platform linux/arm64 <image>
```

## Best Practices

1. **Start Simple**
   - Try easiest method first
   - Don't over-engineer
   - Save complexity for when needed

2. **Document Your Choice**
   - Why you chose this method
   - What alternatives you considered
   - Any gotchas discovered

3. **Version Pin Important Dependencies**
   ```dockerfile
   FROM python:3.11  # Not :latest
   ```

4. **Use Virtual Environments**
   - Python: venv, virtualenv, Poetry
   - Node: nvm
   - Ruby: rbenv
   - Go: go modules

5. **Check Architecture Early**
   - Know your system architecture
   - Verify binary compatibility
   - Plan for Rosetta 2 if needed

6. **Read Official Docs First**
   - README.md
   - INSTALL.md
   - docs/installation

## Anti-Patterns to Avoid

❌ **Don't:** Jump straight to Docker without checking simpler options
✅ **Do:** Check package manager first

❌ **Don't:** Build from source for standard installations
✅ **Do:** Use pre-built binaries when available

❌ **Don't:** Use latest/bleeding-edge versions in production
✅ **Do:** Pin to stable, tested versions

❌ **Don't:** Ignore architecture warnings
✅ **Do:** Verify architecture compatibility upfront

❌ **Don't:** Mix global and local dependencies
✅ **Do:** Use virtual environments consistently

## Related Skills

- **backend-dev-guidelines** - For setting up development environments
- **frontend-dev-guidelines** - For Node/npm environment setup
- **error-tracking** - For monitoring production environments

---

**Remember:** The best installation method is the one that works reliably with the least complexity. Start simple, add complexity only when needed.

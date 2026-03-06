#!/bin/bash

# Phemex Trading Bot - Automated Installation Script
# Supports: Ubuntu/Debian, CentOS/RHEL, Alpine Linux
# Usage: ./install.sh

set -e  # Exit on any error

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

# Detect operating system
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$NAME
        VER=$VERSION_ID
    elif type lsb_release >/dev/null 2>&1; then
        OS=$(lsb_release -si)
        VER=$(lsb_release -sr)
    elif [ -f /etc/lsb-release ]; then
        . /etc/lsb-release
        OS=$DISTRIB_ID
        VER=$DISTRIB_RELEASE
    elif [ -f /etc/debian_version ]; then
        OS=Debian
        VER=$(cat /etc/debian_version)
    else
        OS=$(uname -s)
        VER=$(uname -r)
    fi
    
    print_status "Detected OS: $OS $VER"
}

# Install system dependencies based on OS
install_system_deps() {
    print_status "Installing system dependencies..."
    
    case "$OS" in
        "Ubuntu"* | "Debian"* | "LinuxMint"* | "Pop"*)
            print_status "Installing Debian/Ubuntu packages..."
            sudo apt update
            sudo apt install -y python3 python3-pip python3-venv python3-dev git curl build-essential libssl-dev libffi-dev
            ;;
        "CentOS"* | "Red Hat"* | "Fedora"* | "Rocky"* | "AlmaLinux"*)
            print_status "Installing RHEL/CentOS packages..."
            if command -v dnf &> /dev/null; then
                sudo dnf install -y python3 python3-pip python3-devel git curl gcc openssl-devel libffi-devel
            else
                sudo yum install -y python3 python3-pip python3-devel git curl gcc openssl-devel libffi-devel
            fi
            ;;
        "Alpine"*)
            print_status "Installing Alpine packages..."
            sudo apk update
            sudo apk add python3 py3-pip py3-venv py3-dev git curl build-base openssl-dev libffi-dev
            ;;
        *)
            print_error "Unsupported OS: $OS"
            print_error "Please install Python 3.8+, pip, git manually"
            exit 1
            ;;
    esac
    
    print_success "System dependencies installed"
}

# Verify Python installation
verify_python() {
    print_status "Verifying Python installation..."
    
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
        print_success "Python 3 found: $PYTHON_VERSION"
        
        # Check if version is 3.8 or higher
        PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
        PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)
        
        if [ "$PYTHON_MAJOR" -eq "3" ] && [ "$PYTHON_MINOR" -ge "8" ]; then
            print_success "Python version is compatible (>= 3.8)"
        else
            print_warning "Python version < 3.8 may have compatibility issues"
        fi
    else
        print_error "Python 3 not found"
        exit 1
    fi
}

# Create Python virtual environment
create_venv() {
    print_status "Creating Python virtual environment..."
    
    if [ -d ".venv" ]; then
        print_warning "Virtual environment already exists, removing..."
        rm -rf .venv
    fi
    
    python3 -m venv .venv
    print_success "Virtual environment created"
}

# Install Python dependencies
install_python_deps() {
    print_status "Installing Python dependencies..."
    
    # Activate virtual environment
    source .venv/bin/activate
    
    # Upgrade pip
    pip install --upgrade pip
    
    # Install required packages
    pip install ccxt==4.2.99 pandas pandas_ta matplotlib cryptography
    
    print_success "Python dependencies installed"
}

# Verify installation
verify_installation() {
    print_status "Verifying installation..."
    
    source .venv/bin/activate
    
    # Test imports
    python3 -c "
import sys
print('Python version:', sys.version.split()[0])

try:
    import ccxt
    print('✅ ccxt:', ccxt.__version__)
except ImportError as e:
    print('❌ ccxt:', e)
    sys.exit(1)

try:
    import pandas
    print('✅ pandas:', pandas.__version__)
except ImportError as e:
    print('❌ pandas:', e)
    sys.exit(1)

try:
    import pandas_ta
    print('✅ pandas_ta: installed')
except ImportError as e:
    print('❌ pandas_ta:', e)
    sys.exit(1)

try:
    import matplotlib
    print('✅ matplotlib:', matplotlib.__version__)
except ImportError as e:
    print('❌ matplotlib:', e)
    sys.exit(1)

try:
    import cryptography
    print('✅ cryptography:', cryptography.__version__)
except ImportError as e:
    print('❌ cryptography:', e)
    sys.exit(1)

print('🎉 All dependencies verified successfully!')
"
    
    if [ $? -eq 0 ]; then
        print_success "Installation verification passed"
    else
        print_error "Installation verification failed"
        exit 1
    fi
}

# Create configuration helper scripts
create_helpers() {
    print_status "Creating helper scripts..."
    
    # Create run script
    cat > run_bot.sh << 'EOF'
#!/bin/bash

# Phemex Trading Bot - Runner Script
# Usage: ./run_bot.sh [profile]

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo -e "${RED}[ERROR]${NC} Virtual environment not found. Please run ./install.sh first."
    exit 1
fi

# Activate virtual environment
source .venv/bin/activate

# Check if profile is provided
if [ -z "$1" ]; then
    echo -e "${YELLOW}[USAGE]${NC} ./run_bot.sh [profile]"
    echo ""
    echo "Available profiles:"
    echo "  local_paper    - Paper trading with live market data"
    echo "  phemex_testnet - Exchange-side simulated trading"
    echo "  phemex_live    - Live trading (real money)"
    echo ""
    echo "Examples:"
    echo "  ./run_bot.sh local_paper"
    echo "  ./run_bot.sh phemex_testnet"
    echo "  ./run_bot.sh phemex_live"
    exit 1
fi

# Validate profile
case "$1" in
    "local_paper"|"phemex_testnet"|"phemex_live")
        PROFILE=$1
        ;;
    *)
        echo -e "${RED}[ERROR]${NC} Invalid profile: $1"
        echo "Valid profiles: local_paper, phemex_testnet, phemex_live"
        exit 1
        ;;
esac

# Check for required environment variables for exchange profiles
if [ "$PROFILE" = "phemex_testnet" ] || [ "$PROFILE" = "phemex_live" ]; then
    if [ -z "$PHEMEX_API_KEY" ] || [ -z "$PHEMEX_API_SECRET" ]; then
        echo -e "${RED}[ERROR]${NC} Missing required environment variables:"
        echo "  PHEMEX_API_KEY"
        echo "  PHEMEX_API_SECRET"
        echo ""
        echo "Set them with:"
        echo "  export PHEMEX_API_KEY=\"your_key\""
        echo "  export PHEMEX_API_SECRET=\"your_secret\""
        exit 1
    fi
    
    if [ "$PROFILE" = "phemex_testnet" ] && [ -z "$ENABLE_TESTNET_TRADING" ]; then
        echo -e "${YELLOW}[WARNING]${NC} ENABLE_TESTNET_TRADING not set, running in dry-run mode"
        echo "To enable testnet trading: export ENABLE_TESTNET_TRADING=YES"
    fi
    
    if [ "$PROFILE" = "phemex_live" ] && [ -z "$ENABLE_LIVE_TRADING" ]; then
        echo -e "${YELLOW}[WARNING]${NC} ENABLE_LIVE_TRADING not set, running in dry-run mode"
        echo "To enable live trading: export ENABLE_LIVE_TRADING=YES"
    fi
fi

# Validate configuration
echo -e "${GREEN}[INFO]${NC} Validating configuration..."
python3 -c "
import json
import sys
try:
    from run_bot import validate_config
except ImportError as e:
    print(f'⚠️  Warning: Could not import validate_config: {e}')
    print('⚠️  Skipping configuration validation')
    sys.exit(0)

try:
    with open('config.json', 'r') as f:
        cfg = json.load(f)
    profile_cfg = cfg['profiles']['$PROFILE']
    validate_config(profile_cfg)
    print('✅ Configuration validation passed')
except Exception as e:
    print(f'❌ Configuration validation failed: {e}')
    sys.exit(1)
"
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}[ERROR]${NC} Configuration validation failed"
        exit 1
    fi

# Run the bot
echo -e "${GREEN}[INFO]${NC} Starting bot with profile: $PROFILE"
echo -e "${GREEN}[INFO]${NC} Press Ctrl+C to stop the bot"
echo ""
python3 run_bot.py --profile $PROFILE
EOF

    # Create health check script
    cat > health_check.sh << 'EOF'
#!/bin/bash

# Phemex Trading Bot - Health Check Script
# Usage: ./health_check.sh [profile]

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo -e "${RED}[ERROR]${NC} Virtual environment not found. Please run ./install.sh first."
    exit 1
fi

# Activate virtual environment
source .venv/bin/activate

# Check if profile is provided
if [ -z "$1" ]; then
    echo -e "${YELLOW}[USAGE]${NC} ./health_check.sh [profile]"
    echo "Available profiles: local_paper, phemex_testnet, phemex_live"
    exit 1
fi

# Validate profile
case "$1" in
    "local_paper"|"phemex_testnet"|"phemex_live")
        PROFILE=$1
        ;;
    *)
        echo -e "${RED}[ERROR]${NC} Invalid profile: $1"
        exit 1
        ;;
esac

# Run health check
echo -e "${GREEN}[INFO]${NC} Running health check for profile: $PROFILE"
python3 healthcheck.py --profile $PROFILE
EOF

    # Create status script
    cat > status.sh << 'EOF'
#!/bin/bash

# Phemex Trading Bot - Status Check Script
# Shows recent logs and system status

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}[INFO]${NC} Phemex Trading Bot Status"
echo "=================================="

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo -e "${RED}[ERROR]${NC} Virtual environment not found"
    exit 1
fi

# Check if bot is running
if pgrep -f "run_bot.py" > /dev/null; then
    echo -e "${GREEN}[STATUS]${NC} Bot is running"
else
    echo -e "${YELLOW}[STATUS]${NC} Bot is not running"
fi

# Show recent logs
if [ -f "bot.log" ]; then
    echo ""
    echo -e "${BLUE}[RECENT LOGS]${NC}"
    echo "-------------------"
    tail -20 bot.log
else
    echo -e "${YELLOW}[INFO]${NC} No log file found"
fi

# Show state files
echo ""
echo -e "${BLUE}[STATE FILES]${NC}"
echo "-------------------"
for profile in local_paper phemex_testnet phemex_live; do
    if [ -f "${profile}_state.json" ]; then
        echo -e "${GREEN}✓${NC} ${profile}_state.json"
    elif [ -f "${profile}_state.json.enc" ]; then
        echo -e "${GREEN}✓${NC} ${profile}_state.json.enc (encrypted)"
    fi
    
    if [ -f "${profile}_runtime_state.json" ]; then
        echo -e "${GREEN}✓${NC} ${profile}_runtime_state.json"
    elif [ -f "${profile}_runtime_state.json.enc" ]; then
        echo -e "${GREEN}✓${NC} ${profile}_runtime_state.json.enc (encrypted)"
    fi
done
EOF

    # Make scripts executable
    chmod +x run_bot.sh health_check.sh status.sh
    
    print_success "Helper scripts created"
}

# Create environment template
create_env_template() {
    print_status "Creating environment template..."
    
    cat > .env.template << 'EOF'
# Phemex Trading Bot - Environment Variables Template
# Copy this file to .env and fill in your values

# Exchange API Credentials (REQUIRED for exchange profiles)
PHEMEX_API_KEY=your_api_key_here
PHEMEX_API_SECRET=your_api_secret_here

# Trading Enable Flags
ENABLE_TESTNET_TRADING=NO     # Set to YES to enable testnet trading
ENABLE_LIVE_TRADING=NO        # Set to YES to enable live trading

# Optional: Custom Encryption Key for State Files
# Generate with: python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
BOT_ENCRYPTION_KEY=your_custom_encryption_key_here
EOF
    
    print_success "Environment template created (.env.template)"
}

# Main installation function
main() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  Phemex Trading Bot - Installation${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    
    # Check if running as root (not recommended)
    if [ "$EUID" -eq 0 ]; then
        print_warning "Running as root is not recommended"
        print_warning "Consider creating a non-root user for the bot"
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    # Detect OS
    detect_os
    
    # Install dependencies
    install_system_deps
    
    # Verify Python
    verify_python
    
    # Create virtual environment
    create_venv
    
    # Install Python dependencies
    install_python_deps
    
    # Verify installation
    verify_installation
    
    # Create helper scripts
    create_helpers
    
    # Create environment template
    create_env_template
    
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  Installation Complete!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "${BLUE}Next Steps:${NC}"
    echo ""
    echo "1. Configure environment variables:"
    echo -e "   ${YELLOW}cp .env.template .env${NC}"
    echo -e "   ${YELLOW}nano .env${NC}"
    echo ""
    echo "2. Choose a profile to run:"
    echo -e "   ${GREEN}./run_bot.sh local_paper${NC}     # Paper trading"
    echo -e "   ${GREEN}./run_bot.sh phemex_testnet${NC}   # Testnet trading"
    echo -e "   ${GREEN}./run_bot.sh phemex_live${NC}       # Live trading"
    echo ""
    echo "3. Check bot status:"
    echo -e "   ${GREEN}./status.sh${NC}"
    echo ""
    echo "4. Run health check:"
    echo -e "   ${GREEN}./health_check.sh [profile]${NC}"
    echo ""
    echo -e "${YELLOW}IMPORTANT:${NC} Always start with paper trading first!"
    echo ""
}

# Run main function
main "$@"

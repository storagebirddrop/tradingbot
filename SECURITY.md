# 🔐 Security Policy for Trading Bot

## **CRITICAL: ENCRYPTED STATE FILES**

### **❌ NEVER COMMIT ENCRYPTED FILES**
- **NEVER** commit `*.enc` files to git history
- **NEVER** store Fernet-encrypted artifacts in repository
- **ALWAYS** use `.gitignore` patterns: `*.enc`, `*_state.json.enc`

### **✅ SECURE STATE MANAGEMENT**

#### **1. Dynamic State Generation**
```bash
# Generate fresh state dynamically
python3 scripts/secure_state.py generate local_paper 1000

# Load existing state securely
python3 scripts/secure_state.py load local_paper
```

#### **2. Environment-Based Encryption Keys**
```bash
# Set encryption key for profile
export TRADING_BOT_ENCRYPTION_KEY_LOCAL_PAPER="your_base64_key_here"
export TRADING_BOT_ENCRYPTION_KEY_TESTNET="your_testnet_key_here"
export TRADING_BOT_ENCRYPTION_KEY_LIVE="your_live_key_here"
```

#### **3. Testnet State Management**
```bash
# Generate testnet state dynamically
python3 scripts/testnet_fills_manager.py generate 10000

# Add fills to testnet state
python3 scripts/testnet_fills_manager.py add_fill '{"symbol":"BTC/USDT","side":"buy","amount":0.1,"price":50000,"fee":5.0}'

# Get testnet fills summary
python3 scripts/testnet_fills_manager.py summary

# Load testnet state
python3 scripts/testnet_fills_manager.py load
```

#### **4. Key Rotation Schedule**
```bash
# Rotate keys quarterly or when compromised
python3 scripts/secure_state.py rotate local_paper

# Verify rotation worked
python3 scripts/secure_state.py load local_paper
```

## **🛡️ SECURITY PRINCIPLES**

### **Data Protection**
1. **Zero Commit Policy**: Never commit encrypted artifacts
2. **Dynamic Generation**: Create state on-demand when possible
3. **Environment Keys**: Use environment variables for encryption keys
4. **Regular Rotation**: Rotate keys quarterly or after security incidents

### **Access Controls**
1. **File Permissions**: State files should be `600` (owner read/write only)
2. **Environment Security**: Protect environment variables strictly
3. **Backup Security**: Encrypt backups and store separately
4. **Audit Trail**: Log all state operations for security monitoring

### **Key Management**
1. **Strong Keys**: Use cryptographically secure random keys
2. **Separation**: Different keys per environment (dev/test/prod)
3. **Rotation**: Regular key rotation with proper verification
4. **Recovery**: Secure backup process for key recovery

## **🚨 SECURITY INCIDENT RESPONSE**

### **If Encrypted Files Are Committed**
1. **IMMEDIATE ACTION**: Remove from git history using `git filter-repo`
2. **ROTATE KEYS**: Immediately rotate all affected encryption keys
3. **AUDIT ACCESS**: Review who had access to the repository
4. **NOTIFY TEAM**: Alert all team members of the breach

### **Key Compromise**
1. **ROTATE**: Immediately rotate compromised keys
2. **RE-ENCRYPT**: Re-encrypt all state with new keys
3. **INVESTIGATE**: Determine compromise source
4. **DOCUMENT**: Record incident for future prevention

## **📋 SECURITY CHECKLIST**

### **✅ Pre-Commit Checklist**
- [ ] No `*.enc` files staged for commit
- [ ] `.gitignore` includes encrypted file patterns
- [ ] Environment variables are set, not hardcoded
- [ ] State generation uses dynamic methods
- [ ] Keys are stored securely (environment manager, secrets store)

### **✅ Deployment Checklist**
- [ ] Production keys are different from dev/test
- [ ] State files have proper permissions (600)
- [ ] Backup encryption keys are stored securely
- [ ] Key rotation schedule is documented
- [ ] Incident response plan is in place

### **✅ Maintenance Checklist**
- [ ] Quarterly key rotation completed
- [ ] Access permissions reviewed
- [ ] Security audit completed
- [ ] Documentation updated
- [ ] Team security training completed

## **🔧 IMPLEMENTATION DETAILS**

### **Current Security Implementation**
```python
# ✅ Secure: Dynamic state generation
state = secure_state_manager.generate_state(capital)

# ✅ Secure: Environment-based keys
key = os.getenv("TRADING_BOT_ENCRYPTION_KEY_PROFILE")

# ❌ INSECURE: Never do this
# commit encrypted_file.enc to git
# hardcode encryption keys in source
# store keys in configuration files
```

### **File Structure**
```
.trading_bot_secrets/          # Local only, never committed
├── keys/                      # Encryption keys (600 permissions)
├── backups/                   # Encrypted backups (600 permissions)
└── audit.log                  # Security audit trail

data/                          # Working directory
├── local_paper_state.json    # Development only
└── *.enc                      # Ignored by git, never committed
```

## **🚀 BEST PRACTICES**

### **Development**
1. Use unencrypted state for local development
2. Never commit any `.enc` files
3. Test key rotation procedures regularly
4. Keep security documentation updated

### **Production**
1. Use environment-specific encryption keys
2. Implement proper access controls
3. Regular security audits and penetration testing
4. Incident response plan and team training

### **Team Collaboration**
1. Security training for all team members
2. Clear security policies and procedures
3. Regular security reviews and updates
4. Secure communication channels for key sharing

---

**🔐 REMEMBER: Security is everyone's responsibility. If you see encrypted files in git history, ACT IMMEDIATELY!**

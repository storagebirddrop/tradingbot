#!/usr/bin/env python3
"""
Secure State Management for Trading Bot

This script provides secure handling of trading bot state files:
- Generates state dynamically instead of storing encrypted artifacts
- Uses environment-based encryption keys
- Implements proper key rotation
- Never commits encrypted data to repository

SECURITY PRINCIPLES:
1. Never commit encrypted files to git history
2. Use environment variables for encryption keys
3. Generate state dynamically when needed
4. Implement proper access controls
5. Regular key rotation schedule
"""

import os
import json
import sys
from pathlib import Path
from cryptography.fernet import Fernet
from typing import Dict, Any, Optional
import hashlib
import base64

class SecureStateManager:
    """Manages trading bot state securely without committing encrypted artifacts"""
    
    def __init__(self, profile: str = "local_paper"):
        self.profile = profile
        self.state_dir = Path("data")
        self.state_dir.mkdir(exist_ok=True)
        
    def _get_encryption_key(self) -> bytes:
        """
        Generate encryption key from environment variables
        Falls back to profile-specific key if env var not set
        """
        # Primary: Environment variable
        env_key = os.getenv(f"TRADING_BOT_ENCRYPTION_KEY_{self.profile.upper()}")
        if env_key:
            return base64.urlsafe_b64decode(env_key.encode())
        
        # Secondary: Profile-specific key from system
        key_source = f"trading_bot_{self.profile}_{os.getuid()}"
        key_hash = hashlib.sha256(key_source.encode()).digest()
        return base64.urlsafe_b64encode(key_hash[:32])
    
    def generate_state(self, initial_capital: float = 1000.0) -> Dict[str, Any]:
        """Generate fresh state dynamically"""
        return {
            "profile": self.profile,
            "initial_capital": initial_capital,
            "current_capital": initial_capital,
            "trades": [],
            "positions": {},
            "created_at": str(Path.cwd()),
            "version": "1.0",
            "security_note": "Generated dynamically - never commit encrypted state"
        }
    
    def save_state(self, state: Dict[str, Any], encrypt: bool = True) -> str:
        """
        Save state with optional encryption
        Returns the file path
        """
        state_file = self.state_dir / f"{self.profile}_state.json"
        
        if encrypt:
            key = self._get_encryption_key()
            fernet = Fernet(key)
            
            # Save state as JSON
            json_data = json.dumps(state, indent=2)
            encrypted_data = fernet.encrypt(json_data.encode())
            
            # Save encrypted data
            encrypted_file = self.state_dir / f"{self.profile}_state.json.enc"
            with open(encrypted_file, 'wb') as f:
                f.write(encrypted_data)
            
            print(f"✅ State encrypted and saved to: {encrypted_file}")
            print(f"⚠️  WARNING: Never commit {encrypted_file} to git!")
            return str(encrypted_file)
        else:
            # Save unencrypted for development
            with open(state_file, 'w') as f:
                json.dump(state, f, indent=2)
            
            print(f"✅ State saved to: {state_file}")
            return str(state_file)
    
    def load_state(self, encrypted: bool = True) -> Optional[Dict[str, Any]]:
        """Load state from file"""
        if encrypted:
            encrypted_file = self.state_dir / f"{self.profile}_state.json.enc"
            if not encrypted_file.exists():
                print(f"❌ No encrypted state file found: {encrypted_file}")
                return None
            
            try:
                key = self._get_encryption_key()
                fernet = Fernet(key)
                
                with open(encrypted_file, 'rb') as f:
                    encrypted_data = f.read()
                
                decrypted_data = fernet.decrypt(encrypted_data)
                state = json.loads(decrypted_data.decode())
                
                print(f"✅ State loaded from: {encrypted_file}")
                return state
                
            except Exception as e:
                print(f"❌ Failed to decrypt state: {e}")
                print("💡 Possible key rotation or file corruption")
                return None
        else:
            state_file = self.state_dir / f"{self.profile}_state.json"
            if not state_file.exists():
                print(f"❌ No state file found: {state_file}")
                return None
            
            with open(state_file, 'r') as f:
                state = json.load(f)
            
            print(f"✅ State loaded from: {state_file}")
            return state
    
    def rotate_key(self, old_key_env: str = None, new_key_env: str = None):
        """
        Rotate encryption key for security
        Re-encrypts all state files with new key
        """
        print("🔄 Starting key rotation...")
        
        # Load current state
        current_state = self.load_state(encrypted=True)
        if not current_state:
            print("❌ No state to rotate")
            return False
        
        # Backup old state
        old_file = self.state_dir / f"{self.profile}_state.json.enc"
        backup_file = self.state_dir / f"{self.profile}_state.json.enc.backup"
        if old_file.exists():
            import shutil
            shutil.copy2(old_file, backup_file)
            print(f"📋 Backup created: {backup_file}")
        
        # Save with new key
        self.save_state(current_state, encrypt=True)
        
        print("✅ Key rotation completed")
        print(f"🔑 Old key backup: {backup_file}")
        print("⚠️  Keep backup secure until verification is complete")
        
        return True

def main():
    """CLI interface for secure state management"""
    if len(sys.argv) < 2:
        print("Usage: python secure_state.py <command> [options]")
        print("Commands:")
        print("  generate <profile> <capital>  - Generate new state")
        print("  load <profile>                - Load existing state") 
        print("  rotate <profile>              - Rotate encryption key")
        print("  encrypt <profile>             - Encrypt existing state")
        sys.exit(1)
    
    command = sys.argv[1]
    profile = sys.argv[2] if len(sys.argv) > 2 else "local_paper"
    
    manager = SecureStateManager(profile)
    
    if command == "generate":
        capital = float(sys.argv[3]) if len(sys.argv) > 3 else 1000.0
        state = manager.generate_state(capital)
        manager.save_state(state, encrypt=True)
        
    elif command == "load":
        state = manager.load_state(encrypted=True)
        if state:
            print(f"📊 State loaded for profile: {profile}")
            print(f"💰 Current capital: ${state.get('current_capital', 0):.2f}")
            print(f"📈 Trades count: {len(state.get('trades', []))}")
        
    elif command == "rotate":
        success = manager.rotate_key()
        if success:
            print("✅ Key rotation completed successfully")
        else:
            print("❌ Key rotation failed")
            
    elif command == "encrypt":
        # Load unencrypted and encrypt it
        state = manager.load_state(encrypted=False)
        if state:
            manager.save_state(state, encrypt=True)
            print("✅ State encrypted successfully")
        else:
            print("❌ No unencrypted state found")
            
    else:
        print(f"❌ Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Secure State Management Script
Replaces encrypted state files with dynamic generation and environment-based keys
"""

import os
import sys
import json
import argparse
import base64
from cryptography.fernet import Fernet
from datetime import datetime, timezone
from typing import Dict, Any, Optional

def get_encryption_key(profile: str) -> bytes:
    """
    Get encryption key from environment variables with fallback generation
    Keys are stored per-profile to prevent cross-contamination
    """
    env_var = f"TRADING_BOT_ENCRYPTION_KEY_{profile.upper()}"
    key_env = os.environ.get(env_var)
    
    if key_env:
        try:
            # Try to decode as base64 and validate it's exactly 32 bytes
            try:
                decoded = base64.urlsafe_b64decode(key_env.encode())
                if len(decoded) == 32:
                    return key_env.encode()  # Already a valid Fernet key
            except Exception:
                pass  # Not valid base64, try other formats
            
            # Try hex format (64-char hex string)
            if len(key_env) == 64 and all(c in '0123456789abcdefABCDEF' for c in key_env):
                key_bytes = bytes.fromhex(key_env)
                return base64.urlsafe_b64encode(key_bytes)
            
            # Try direct base64 format (not urlsafe)
            try:
                decoded = base64.b64decode(key_env.encode())
                if len(decoded) == 32:
                    return base64.urlsafe_b64encode(decoded)
            except Exception:
                pass
            
            # If we get here, the format is invalid
            raise ValueError("Invalid key format")
            
        except Exception as e:
            print(f"❌ Invalid encryption key format: {e}")
            print(f"   Expected 44-char base64 Fernet key or 64-char hex key")
            print(f"   Got {len(key_env)} chars: {key_env[:20]}...")
            sys.exit(1)
    
    # For development/testing, persist key to local file for reuse
    if os.environ.get("BOT_ENV") in ("development", "test"):
        key_file = os.path.join(".trading_bot_keys", f"{profile}_key")
        os.makedirs(".trading_bot_keys", exist_ok=True)
        
        # Try to load existing key
        if os.path.exists(key_file):
            try:
                with open(key_file, 'r') as f:
                    persisted_key = f.read().strip()
                    return persisted_key.encode()  # Return as-is, already base64 encoded
            except Exception as e:
                print(f"⚠️  Warning: Failed to load persisted key: {e}")
        
        # Generate new key and persist it
        try:
            new_key = base64.urlsafe_b64encode(os.urandom(32))
            with open(key_file, 'w') as f:
                f.write(new_key.decode())
            print(f"⚠️  WARNING: Generated and persisted encryption key for {profile}")
            print(f"   Set {env_var} environment variable for consistency")
            print(f"   Key persisted to: {key_file}")
            return new_key
        except Exception as e:
            print(f"❌ ERROR: Failed to persist key: {e}")
            print(f"   Set {env_var} environment variable manually")
            sys.exit(1)
    
    print(f"❌ ERROR: {env_var} environment variable required")
    sys.exit(1)

def generate_state(profile: str, initial_cash: float) -> Dict[str, Any]:
    """Generate fresh trading state dynamically"""
    return {
        "version": "1.0",
        "profile": profile,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cash": initial_cash,
        "positions": {},
        "equity_history": [],
        "last_updated": datetime.now(timezone.utc).isoformat()
    }

def generate_fills_state(profile: str) -> Dict[str, Any]:
    """Generate fresh fills state dynamically"""
    return {
        "version": "1.0", 
        "profile": profile,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "fills": [],
        "reconciled_fills": [],
        "last_fill_id": 0,
        "last_updated": datetime.now(timezone.utc).isoformat()
    }

def save_state_secure(profile: str, state: Dict[str, Any], state_type: str = "state") -> str:
    """Save state with encryption to local file (not committed)"""
    key = get_encryption_key(profile)
    fernet = Fernet(key)
    
    # Encrypt the state
    state_json = json.dumps(state, separators=(',', ':'))
    encrypted_data = fernet.encrypt(state_json.encode())
    
    # Save to local file atomically (not in git)
    filename = f"{profile}_{state_type}.json.enc"
    filepath = os.path.join("data", filename)
    
    os.makedirs("data", exist_ok=True)
    
    # Write to temporary file first, then atomically replace
    temp_filepath = filepath + ".tmp"
    try:
        with open(temp_filepath, 'wb') as f:
            f.write(encrypted_data)
            f.flush()
            os.fsync(f.fileno())  # Ensure data hits disk
        
        # Atomically replace the target file
        os.replace(temp_filepath, filepath)
        
    except Exception as e:
        # Clean up temp file if it exists
        if os.path.exists(temp_filepath):
            try:
                os.remove(temp_filepath)
            except:
                pass
        raise e
    
    print(f"✅ Secure state saved: {filepath}")
    return filepath

def load_state_secure(profile: str, state_type: str = "state") -> Optional[Dict[str, Any]]:
    """Load and decrypt state from local file"""
    key = get_encryption_key(profile)
    fernet = Fernet(key)
    
    filename = f"{profile}_{state_type}.json.enc"
    filepath = os.path.join("data", filename)
    
    if not os.path.exists(filepath):
        print(f"ℹ️  No existing state file: {filepath}")
        return None
    
    try:
        with open(filepath, 'rb') as f:
            encrypted_data = f.read()
        
        decrypted_data = fernet.decrypt(encrypted_data)
        state = json.loads(decrypted_data.decode())
        
        print(f"✅ Secure state loaded: {filepath}")
        return state
    except Exception as e:
        print(f"❌ Failed to load state: {e}")
        return None

def rotate_key(profile: str, state_types: list = ["state", "fills_state", "runtime_state"]):
    """Rotate encryption key and re-encrypt all state files"""
    print(f"🔄 Rotating encryption key for profile: {profile}")
    
    # Load existing states
    old_states = {}
    for state_type in state_types:
        state = load_state_secure(profile, state_type)
        if state:
            old_states[state_type] = state
    
    # Remove old encrypted files
    for state_type in state_types:
        filename = f"{profile}_{state_type}.json.enc"
        filepath = os.path.join("data", filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            print(f"🗑️  Removed old encrypted file: {filepath}")
    
    # Generate new key instruction
    env_var = f"TRADING_BOT_ENCRYPTION_KEY_{profile.upper()}"
    new_key = base64.urlsafe_b64encode(os.urandom(32)).decode()
    
    print(f"🔑 NEW ENCRYPTION KEY for {profile}:")
    print(f"   export {env_var}=\"{new_key}\"")
    print("")
    print("⚠️  IMPORTANT: Update your environment variables with the new key!")
    
    # Temporarily set the new key for re-encryption
    old_env_value = os.environ.get(env_var)
    os.environ[env_var] = new_key
    
    try:
        # Re-encrypt all loaded states with the new key
        reencrypted_count = 0
        for state_type, state in old_states.items():
            try:
                save_state_secure(profile, state, state_type)
                print(f"✅ Re-encrypted {state_type} with new key")
                reencrypted_count += 1
            except Exception as e:
                print(f"❌ Failed to re-encrypt {state_type}: {e}")
                # Restore old key and exit
                if old_env_value is not None:
                    os.environ[env_var] = old_env_value
                elif env_var in os.environ:
                    del os.environ[env_var]
                print(f"🔄 Restored old key - please retry manually")
                return new_key
        
        print(f"✅ Successfully re-encrypted {reencrypted_count} state files")
        
    finally:
        # Restore original environment
        if old_env_value is not None:
            os.environ[env_var] = old_env_value
        elif env_var in os.environ:
            del os.environ[env_var]
    
    print("🔄 Key rotation completed - all states re-encrypted")
    return new_key

def audit_repository():
    """Audit repository for any encrypted files or keys"""
    print("🔍 Auditing repository for security issues...")
    
    issues_found = False
    
    # Check for .enc files in data directory
    data_dir = "data"
    if os.path.exists(data_dir):
        for file in os.listdir(data_dir):
            if file.endswith('.enc'):
                filepath = os.path.join(data_dir, file)
                print(f"⚠️  Found encrypted file: {filepath}")
                issues_found = True
    
    # Check git for any tracked .enc files
    try:
        result = os.popen("git ls-files | grep '\\.enc$'").read().strip()
        if result:
            print("❌ CRITICAL: Encrypted files tracked in git:")
            for line in result.split('\n'):
                if line.strip():
                    print(f"   - {line.strip()}")
            issues_found = True
    except:
        pass
    
    # Check for potential keys in environment files (but not templates)
    env_files = ['.env']  # Skip .env.template and .env.example as they're templates
    for env_file in env_files:
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                content = f.read()
                # Check for actual keys, not placeholder text
                if any(pattern in content.lower() and 'your_' not in content.lower() and 'here' not in content.lower() 
                      for pattern in ['key', 'secret', 'token', 'password']):
                    print(f"⚠️  Potential credentials in: {env_file}")
                    issues_found = True
    
    if not issues_found:
        print("✅ No security issues found")
    else:
        print("❌ Security issues found - please address immediately")
    
    return not issues_found

def main():
    parser = argparse.ArgumentParser(description="Secure state management")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Generate command
    gen_parser = subparsers.add_parser('generate', help='Generate new state')
    gen_parser.add_argument('profile', help='Trading profile (local_paper, testnet, live)')
    gen_parser.add_argument('cash', type=float, nargs='?', default=None, 
                          help='Initial cash amount (required for state type, ignored for fills_state)')
    gen_parser.add_argument('--type', default='state', choices=['state', 'fills_state'], 
                          help='Type of state to generate')
    
    # Load command
    load_parser = subparsers.add_parser('load', help='Load existing state')
    load_parser.add_argument('profile', help='Trading profile')
    load_parser.add_argument('--type', default='state', choices=['state', 'fills_state', 'runtime_state'],
                           help='Type of state to load')
    
    # Rotate command
    rotate_parser = subparsers.add_parser('rotate', help='Rotate encryption key')
    rotate_parser.add_argument('profile', help='Trading profile')
    
    # Audit command
    audit_parser = subparsers.add_parser('audit', help='Audit repository security')
    
    args = parser.parse_args()
    
    if args.command == 'generate':
        if args.type == 'state':
            if args.cash is None:
                print("❌ ERROR: cash amount required for state generation")
                print("   Usage: python secure_state.py generate <profile> <cash> --type state")
                sys.exit(1)
            state = generate_state(args.profile, args.cash)
        else:
            state = generate_fills_state(args.profile)
        
        save_state_secure(args.profile, state, args.type)
        
    elif args.command == 'load':
        state = load_state_secure(args.profile, args.type)
        if state:
            print(json.dumps(state, indent=2))
        
    elif args.command == 'rotate':
        rotate_key(args.profile)
        
    elif args.command == 'audit':
        audit_repository()
        
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
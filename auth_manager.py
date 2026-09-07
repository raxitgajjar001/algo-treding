import json
import uuid
import hashlib
import time
from pathlib import Path
from typing import Optional, Tuple

AUTH_FILE = Path(__file__).resolve().parent / 'data' / 'auth.json'

AUTHORIZED_USER = 'Raxit@5001'
AUTHORIZED_PIN = '030570'

DEFAULT_AUTH = {
    'username': AUTHORIZED_USER,
    'password_hash': hashlib.sha256('Raxit@9601'.encode('utf-8')).hexdigest(),
    'recovery_pin': AUTHORIZED_PIN,
    'created_at': time.time(),
    'updated_at': time.time()
}

active_sessions = set()

def load_auth():
    if AUTH_FILE.exists():
        try:
            with open(AUTH_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                data['username'] = AUTHORIZED_USER  # Strictly only authorized user
                if 'recovery_pin' not in data or data.get('recovery_pin') != AUTHORIZED_PIN:
                    data['recovery_pin'] = AUTHORIZED_PIN
                return data
        except Exception:
            pass
    save_auth(DEFAULT_AUTH)
    return DEFAULT_AUTH.copy()

def save_auth(auth_data):
    AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(AUTH_FILE, 'w', encoding='utf-8') as f:
        json.dump(auth_data, f, indent=2)

def verify_login(username: str, password: str) -> Optional[str]:
    # Strictly reject any username other than Raxit@5001
    if username.strip() != AUTHORIZED_USER:
        return None
    auth = load_auth()
    input_hash = hashlib.sha256(password.strip().encode('utf-8')).hexdigest()
    if input_hash == auth.get('password_hash'):
        token = f'sess-{uuid.uuid4().hex}'
        active_sessions.add(token)
        return token
    return None

def validate_token(token: str) -> bool:
    if not token:
        return False
    return token in active_sessions

def invalidate_token(token: str):
    active_sessions.discard(token)

def change_credentials(old_password: str, new_username: str, new_password: str) -> Tuple[bool, str]:
    auth = load_auth()
    old_hash = hashlib.sha256(old_password.strip().encode('utf-8')).hexdigest()
    if old_hash != auth.get('password_hash'):
        return False, 'Incorrect Old Password'
    
    if len(new_password.strip()) < 4:
        return False, 'Password must be at least 4 characters'
    
    new_hash = hashlib.sha256(new_password.strip().encode('utf-8')).hexdigest()
    auth['username'] = AUTHORIZED_USER  # Strictly maintain only authorized user ID
    auth['password_hash'] = new_hash
    auth['updated_at'] = time.time()
    save_auth(auth)
    return True, 'Password updated successfully!'

def verify_recovery_pin(username: str, pin: str) -> Tuple[bool, str]:
    if username.strip() != AUTHORIZED_USER:
        return False, 'Invalid User ID. Only authorized user allowed.'
    auth = load_auth()
    expected_pin = str(auth.get('recovery_pin', AUTHORIZED_PIN)).strip()
    if pin.strip() != expected_pin:
        return False, 'Incorrect Recovery PIN. Access Denied!'
    return True, 'Recovery PIN verified successfully.'

def reset_password_with_pin(username: str, pin: str, new_password: str) -> Tuple[bool, str]:
    ok, msg = verify_recovery_pin(username, pin)
    if not ok:
        return False, msg
    
    if len(new_password.strip()) < 4:
        return False, 'New password must be at least 4 characters.'
    
    auth = load_auth()
    auth['password_hash'] = hashlib.sha256(new_password.strip().encode('utf-8')).hexdigest()
    auth['updated_at'] = time.time()
    save_auth(auth)
    return True, 'Password reset successfully!'

def reset_password(username: str, new_password: str) -> Tuple[bool, str]:
    return reset_password_with_pin(username, AUTHORIZED_PIN, new_password)

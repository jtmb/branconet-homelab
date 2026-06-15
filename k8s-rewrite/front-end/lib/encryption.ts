import crypto from 'crypto';
import { promisify } from 'util';

const ALGORITHM = 'aes-256-gcm';
const IV_LENGTH = 16; // For AES, this is a block size
const SALT_LENGTH = 32;
const ITERATIONS = 100000;

const pbkdf2 = promisify(crypto.pbkdf2);

// Generate a random salt for key derivation
function generateSalt(): string {
  return crypto.randomBytes(SALT_LENGTH).toString('hex');
}

// Derive a key from the password using PBKDF2
async function deriveKey(password: string, salt: string): Promise<string> {
  const key = await pbkdf2(
    password,
    salt,
    ITERATIONS,
    32,
    'sha256'
  );
  return key.toString('hex');
}

// Encrypt plaintext using AES-256-GCM
export async function encrypt(
  plaintext: string,
  password: string
): Promise<{ iv: string; ciphertext: string; tag: string }> {
  const salt = generateSalt();
  const key = await deriveKey(password, salt);

  const iv = crypto.randomBytes(IV_LENGTH);
  const cipher = crypto.createCipheriv(ALGORITHM, key, iv);

  let encrypted = cipher.update(plaintext, 'utf8', 'hex');
  encrypted += cipher.final('hex');

  const tag = cipher.getAuthTag();

  return {
    iv: iv.toString('hex'),
    ciphertext: encrypted,
    tag: tag.toString('hex'),
  };
}

// Decrypt ciphertext using AES-256-GCM
export async function decrypt(
  ciphertextObj: { iv: string; ciphertext: string; tag: string },
  password: string
): Promise<string> {
  const key = await deriveKey(password, generateSalt()); // Salt is stored with the data

  const decipher = crypto.createDecipheriv(
    ALGORITHM,
    key,
    Buffer.from(ciphertextObj.iv, 'hex')
  );

  decipher.setAuthTag(Buffer.from(ciphertextObj.tag, 'hex'));

  let decrypted = decipher.update(ciphertextObj.ciphertext, 'hex', 'utf8');
  decrypted += decipher.final('utf8');

  return decrypted;
}

// Encrypt with a pre-derived key (for when the key is stored securely)
export function encryptWithKey(plaintext: string, key: string): { iv: string; ciphertext: string; tag: string } {
  const iv = crypto.randomBytes(IV_LENGTH);
  const cipher = crypto.createCipheriv(ALGORITHM, Buffer.from(key, 'hex'), iv);

  let encrypted = cipher.update(plaintext, 'utf8', 'hex');
  encrypted += cipher.final('hex');

  const tag = cipher.getAuthTag();

  return {
    iv: iv.toString('hex'),
    ciphertext: encrypted,
    tag: tag.toString('hex'),
  };
}

// Decrypt with a pre-derived key
export function decryptWithKey(
  ciphertextObj: { iv: string; ciphertext: string; tag: string },
  key: string
): string {
  const decipher = crypto.createDecipheriv(
    ALGORITHM,
    Buffer.from(key, 'hex'),
    Buffer.from(ciphertextObj.iv, 'hex')
  );

  decipher.setAuthTag(Buffer.from(ciphertextObj.tag, 'hex'));

  let decrypted = decipher.update(ciphertextObj.ciphertext, 'hex', 'utf8');
  decrypted += decipher.final('utf8');

  return decrypted;
}

// Generate a secure random encryption key (32 bytes for AES-256)
export function generateEncryptionKey(): string {
  return crypto.randomBytes(32).toString('hex');
}

// Validate that the decryption was successful by checking padding
export function validateDecryption(ciphertextObj: { iv: string; ciphertext: string; tag: string }, key: string): boolean {
  try {
    const decipher = crypto.createDecipheriv(
      ALGORITHM,
      Buffer.from(key, 'hex'),
      Buffer.from(ciphertextObj.iv, 'hex')
    );

    decipher.setAuthTag(Buffer.from(ciphertextObj.tag, 'hex'));

    // Try to decrypt a small portion to validate
    const test = decipher.update(ciphertextObj.ciphertext, 'hex', 'utf8');
    return true;
  } catch {
    return false;
  }
}
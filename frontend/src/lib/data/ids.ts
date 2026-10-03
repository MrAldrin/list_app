// Client-made IDs: `op_id`s and new list or item `uid`s.

type CryptoLike = Pick<Crypto, 'getRandomValues'> & { randomUUID?: () => string };

/**
 * A random UUID v4 string (lowercase, with hyphens).
 *
 * `crypto.randomUUID` exists only in secure contexts (HTTPS or localhost). The
 * iPhone test opens the app over plain HTTP on the local network, so we fall
 * back to `crypto.getRandomValues`, which works everywhere.
 */
export function newId(cryptoImpl: CryptoLike = globalThis.crypto): string {
	if (typeof cryptoImpl.randomUUID === 'function') return cryptoImpl.randomUUID();

	const bytes = cryptoImpl.getRandomValues(new Uint8Array(16));
	bytes[6] = (bytes[6] & 0x0f) | 0x40; // version 4
	bytes[8] = (bytes[8] & 0x3f) | 0x80; // variant 10xx
	const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
	return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

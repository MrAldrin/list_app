import { Effect } from 'effect';
import { apiError } from './api';

const BCRYPT_BYTES = 72;
const BCRYPT_COST = 12;
const bcryptHash = /^\$2[abxy]\$(?:0[4-9]|[12][0-9]|3[01])\$[./A-Za-z0-9]{53}$/;

export function validateNewRoomPassword(password: string): void {
	// The historical rule uses Unicode whitespace, including U+0085 but not U+FEFF.
	if ([...password].every((c) => /\p{White_Space}/u.test(c) || (c >= '\x1c' && c <= '\x1f'))) {
		throw apiError(422, 'invalid_request', 'Password cannot be empty');
	}
	if (Array.from(password).length < 4) {
		throw apiError(422, 'invalid_request', 'Password must be at least 4 characters');
	}
	if (Buffer.byteLength(password, 'utf8') > BCRYPT_BYTES) {
		throw apiError(422, 'invalid_request', 'The password cannot be longer than 72 bytes');
	}
}

export function verifyRoomPassword(password: string, hash: unknown) {
	// Do not use Bun's bcrypt pre-hashing for passwords longer than 72 bytes.
	if (
		typeof hash !== 'string' ||
		hash.length !== 60 ||
		!bcryptHash.test(hash) ||
		Buffer.byteLength(password, 'utf8') > BCRYPT_BYTES
	) {
		return Effect.succeed(false);
	}
	// Bun rejects empty inputs. For bcrypt an empty input and a single zero
	// byte have the same key (all zeroes); this keeps old hashes verifiable.
	return Effect.promise(async () => {
		try {
			return await Bun.password.verify(password || '\0', hash, 'bcrypt');
		} catch (error) {
			if (error instanceof Error && 'code' in error && error.code === 'PASSWORD_INVALID_ENCODING') {
				return false;
			}
			throw error;
		}
	});
}

// Call validateNewRoomPassword first, and hash outside the transaction.
export function hashRoomPassword(password: string) {
	return Effect.promise(() =>
		Bun.password.hash(password, { algorithm: 'bcrypt', cost: BCRYPT_COST })
	);
}

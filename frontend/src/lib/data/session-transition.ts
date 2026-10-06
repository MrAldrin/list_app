/**
 * Serializes room-cookie sign-in, sign-out and access revalidation across tabs.
 * The IndexedDB marker remains authoritative; a lock only orders requests.
 */
export type SessionLockManager = Pick<LockManager, 'request'>;

export interface SessionLockResult<T> {
	acquired: boolean;
	value?: T;
}

const signinListeners = new Set<(slug: string) => void>();
let signinChannel: BroadcastChannel | null = null;

function roomSigninChannel(): BroadcastChannel | null {
	if (typeof window === 'undefined' || typeof BroadcastChannel === 'undefined') return null;
	if (!signinChannel) {
		try {
			signinChannel = new BroadcastChannel('listr:room-session');
			signinChannel.addEventListener('message', (event: MessageEvent<unknown>) => {
				if (
					typeof event.data === 'object' &&
					event.data !== null &&
					(event.data as { type?: unknown }).type === 'signed-in' &&
					typeof (event.data as { slug?: unknown }).slug === 'string'
				) {
					for (const listener of signinListeners) {
						try {
							listener((event.data as { slug: string }).slug);
						} catch {
							// A hint listener cannot interrupt another tab's transition.
						}
					}
				}
			});
		} catch {
			signinChannel = null;
		}
	}
	return signinChannel;
}

export function announceRoomSignIn(slug: string): void {
	try {
		roomSigninChannel()?.postMessage({ type: 'signed-in', slug });
	} catch {
		// The durable sign-out marker and API access checks remain authoritative.
	}
}

export function onRoomSignIn(listener: (slug: string) => void): () => void {
	signinListeners.add(listener);
	roomSigninChannel();
	return () => signinListeners.delete(listener);
}

export function browserSessionLocks(): SessionLockManager | null {
	if (typeof navigator === 'undefined' || !('locks' in navigator)) return null;
	return navigator.locks;
}

export async function withRoomSessionLock<T>(
	slug: string,
	operation: () => Promise<T>,
	locks: SessionLockManager | null = browserSessionLocks()
): Promise<SessionLockResult<T>> {
	if (!locks) return { acquired: false };
	const name = `listr:room-session:${encodeURIComponent(slug)}`;
	const value = await locks.request(name, { mode: 'exclusive' }, operation);
	return { acquired: true, value };
}

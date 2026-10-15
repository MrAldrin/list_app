import type { Item, List, Room } from '#lib/data/types.ts';
import type {
	RoomIdentity,
	ShareIdentity,
	SnapshotClearHint,
	SnapshotData,
	SnapshotIdentity
} from './snapshot-store';

export interface StoredControl {
	key: string;
	identity: SnapshotIdentity;
	generation: number;
	signOut?: { pendingServerLogout: boolean };
}

export function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function nonEmptyString(value: unknown): value is string {
	return typeof value === 'string' && value.length > 0;
}

export function validIdentity(value: unknown): value is SnapshotIdentity {
	if (!isRecord(value)) return false;
	if (value.kind === 'room') return nonEmptyString(value.slug) && value.slug.length <= 2048;
	if (value.kind === 'share') return nonEmptyString(value.token) && value.token.length <= 2048;
	return false;
}

export function sameIdentity(a: SnapshotIdentity, b: SnapshotIdentity): boolean {
	return (
		a.kind === b.kind &&
		('slug' in a ? a.slug === (b as RoomIdentity).slug : a.token === (b as ShareIdentity).token)
	);
}

export function isSequence(value: unknown): value is number {
	return Number.isSafeInteger(value) && (value as number) >= 0;
}

function validTags(value: unknown): value is string[] {
	return Array.isArray(value) && value.every((tag) => typeof tag === 'string');
}

function validList(value: unknown, seq: number): value is List {
	if (!isRecord(value) || !nonEmptyString(value.uid)) return false;
	if (typeof value.slug !== 'string' || typeof value.name !== 'string' || !validTags(value.tags))
		return false;
	if (
		!isRecord(value.hide_done) ||
		!['off', 'all', 'age', 'recent'].includes(String(value.hide_done.mode))
	)
		return false;
	if (
		!Number.isSafeInteger(value.hide_done.age_days) ||
		(value.hide_done.age_days as number) < 1 ||
		(value.hide_done.age_days as number) > 100_000 ||
		!Number.isSafeInteger(value.hide_done.recent_count) ||
		(value.hide_done.recent_count as number) < 1 ||
		(value.hide_done.recent_count as number) > 100_000
	)
		return false;
	return isSequence(value.changed_seq) && value.changed_seq <= seq;
}

function validItem(value: unknown, seq: number): value is Item {
	if (!isRecord(value) || !nonEmptyString(value.uid) || !nonEmptyString(value.list_uid))
		return false;
	if (typeof value.name !== 'string' || typeof value.description !== 'string') return false;
	if (
		typeof value.done !== 'boolean' ||
		!Number.isSafeInteger(value.quantity) ||
		(value.quantity as number) < 1
	)
		return false;
	if (value.completed_at !== null && typeof value.completed_at !== 'string') return false;
	if (typeof value.completed_at === 'string' && !Number.isFinite(Date.parse(value.completed_at)))
		return false;
	if (!value.done && value.completed_at !== null) return false;
	return validTags(value.tags) && isSequence(value.changed_seq) && value.changed_seq <= seq;
}

function copyList(list: List): List {
	return {
		uid: list.uid,
		slug: list.slug,
		name: list.name,
		tags: [...list.tags],
		hide_done: {
			mode: list.hide_done.mode,
			age_days: list.hide_done.age_days,
			recent_count: list.hide_done.recent_count
		},
		changed_seq: list.changed_seq
	};
}

function copyItem(item: Item): Item {
	return {
		uid: item.uid,
		list_uid: item.list_uid,
		name: item.name,
		done: item.done,
		completed_at: item.completed_at,
		quantity: item.quantity,
		description: item.description,
		tags: [...item.tags],
		changed_seq: item.changed_seq
	};
}

export function validateData(identity: SnapshotIdentity, data: unknown): SnapshotData | null {
	if (
		!isRecord(data) ||
		!isSequence(data.seq) ||
		!Array.isArray(data.lists) ||
		!Array.isArray(data.items)
	)
		return null;
	if (identity.kind === 'room') {
		if (
			!isRecord(data.room) ||
			data.room.slug !== identity.slug ||
			typeof data.room.name !== 'string'
		)
			return null;
	} else if (data.lists.length !== 1) {
		return null;
	}
	if (!data.lists.every((list) => validList(list, data.seq as number))) return null;
	if (!data.items.every((item) => validItem(item, data.seq as number))) return null;
	const listIds = new Set(data.lists.map((list) => (list as List).uid));
	const itemIds = new Set(data.items.map((item) => (item as Item).uid));
	if (listIds.size !== data.lists.length || itemIds.size !== data.items.length) return null;
	if (data.items.some((item) => !listIds.has((item as Item).list_uid))) return null;
	if (identity.kind === 'share') {
		const listUid = (data.lists[0] as List).uid;
		if (data.items.some((item) => (item as Item).list_uid !== listUid)) return null;
	}
	return {
		seq: data.seq as number,
		room: identity.kind === 'room' ? { slug: identity.slug, name: (data.room as Room).name } : null,
		lists: (data.lists as List[]).map(copyList),
		items: (data.items as Item[]).map(copyItem)
	};
}

export function validControl(
	value: unknown,
	key: string,
	identity: SnapshotIdentity
): value is StoredControl {
	if (
		!isRecord(value) ||
		value.key !== key ||
		!validIdentity(value.identity) ||
		!sameIdentity(value.identity, identity) ||
		!isSequence(value.generation)
	)
		return false;
	if (value.signOut !== undefined) {
		if (
			identity.kind !== 'room' ||
			!isRecord(value.signOut) ||
			typeof value.signOut.pendingServerLogout !== 'boolean'
		)
			return false;
	}
	return true;
}

export function parseClearHint(value: unknown): SnapshotClearHint | null {
	if (
		!isRecord(value) ||
		value.type !== 'snapshot-clear' ||
		!validIdentity(value.identity) ||
		!isSequence(value.generation)
	)
		return null;
	return {
		identity:
			value.identity.kind === 'room'
				? { kind: 'room', slug: value.identity.slug }
				: { kind: 'share', token: value.identity.token },
		generation: value.generation
	};
}

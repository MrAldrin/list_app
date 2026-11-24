import { SqliteClient } from '@effect/sql-sqlite-bun';
import { Effect } from 'effect';
import { randomBytes } from 'node:crypto';
import { listKey } from './op-name-keys';
import { apiError } from './api';
import { Refusal, textField, uuid, version, type Operation, type Scope } from './op-domain';
export type ListRow = { id: number; uid: string; name: string; slug: string; changed_seq: number };

export function findTarget(scope: Scope, uid: string) {
	return Effect.gen(function* () {
		const sql = yield* SqliteClient.SqliteClient;
		const [row] =
			yield* sql<ListRow>`SELECT id, uid,name,slug,changed_seq FROM lists WHERE room_id=${scope.roomId} AND uid=${uuid(uid)}`;
		return row && (!scope.sharedList || row.id === scope.sharedList.id) ? row : undefined;
	});
}
export function freshUid(uid: string | undefined) {
	return Effect.gen(function* () {
		if (!uid) return crypto.randomUUID();
		const sql = yield* SqliteClient.SqliteClient;
		const id = uuid(uid);
		const rows =
			yield* sql`SELECT uid FROM lists WHERE uid=${id} UNION ALL SELECT uid FROM items WHERE uid=${id} UNION ALL SELECT uid FROM deletions WHERE uid=${id} LIMIT 1`;
		if (rows.length) return yield* apiError(422, 'invalid_request', 'This uid is already used.');
		return id;
	});
}
export function applyList(
	scope: Scope,
	op: Extract<Operation, { type: 'room.rename' | 'list.create' | 'list.rename' | 'list.delete' }>,
	target?: ListRow
) {
	return Effect.gen(function* () {
		const sql = yield* SqliteClient.SqliteClient;
		if (op.type === 'room.rename') {
			const name = yield* textField(op.name, 'Name');
			yield* sql`UPDATE rooms SET name=${name} WHERE id=${scope.roomId} AND name!=${name}`;
			return {};
		}
		if (op.type === 'list.delete' && target) {
			yield* sql`DELETE FROM items WHERE list_id=${target.id}`;
			yield* sql`DELETE FROM lists WHERE id=${target.id}`;
			return {};
		}
		if (op.type === 'list.delete' || (op.type === 'list.rename' && !target))
			return yield* unavailableList();
		const uid = op.type === 'list.create' ? yield* freshUid(op.uid) : undefined;
		const name = yield* textField(op.name, 'Name');
		const lists =
			yield* sql<ListRow>`SELECT id,uid,slug,name,changed_seq FROM lists WHERE room_id=${scope.roomId}`;
		const existing = lists.find(
			(row) => row.id !== target?.id && listKey(row.name) === listKey(name)
		);
		if (op.type === 'list.create' && uid) {
			if (existing) return { created: false, list_uid: existing.uid, slug: existing.slug };
			if (lists.length >= 100)
				return yield* new Refusal({
					code: 'too_many',
					message: 'A room can have at most 100 lists'
				});
			const slug = `${name.toLowerCase().replace(/[^a-z0-9]/gu, '-')}-${crypto.randomUUID().slice(0, 6)}`;
			yield* sql`INSERT INTO lists(name,slug,room_id,share_token,uid) VALUES (${name},${slug},${scope.roomId},${randomBytes(32).toString('base64url')},${uid})`;
			return { created: true, list_uid: uid, slug };
		}
		if (op.type !== 'list.rename' || !target) return yield* unavailableList();
		yield* version(op.base_seq, target.changed_seq, target.name === name);
		if (existing)
			return yield* new Refusal({
				code: 'duplicate_name',
				message: `'${name}' already exists in this room`
			});
		if (name !== target.name) yield* sql`UPDATE lists SET name=${name} WHERE id=${target.id}`;
		const [row] = yield* sql<{
			changed_seq: number;
		}>`SELECT changed_seq FROM lists WHERE id=${target.id}`;
		return { changed_seq: row.changed_seq };
	});
}
export function unavailableList() {
	return new Refusal({ code: 'list_unavailable', message: 'The list is no longer available.' });
}

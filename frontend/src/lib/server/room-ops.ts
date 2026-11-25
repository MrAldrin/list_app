import { createHash } from 'node:crypto';
import { SqliteClient } from '@effect/sql-sqlite-bun';
import { Effect, Schema } from 'effect';
import { OpResponse, SentOp, SentShareOp } from '#lib/contracts/v1/ops.ts';
import { apiError } from './api';
import { wakeRoomStreams } from './live-streams';
import { requireRoomAccess } from './room-access';
import { timestamp, uuid, type Answer, type Operation, type Result, type Scope } from './op-domain';
import { applyItem } from './op-items';
import { applyList, findTarget, unavailableList, type ListRow } from './op-lists';
import { applyTagOp } from './op-tags';

// All operation fields are scalars or arrays of scalars. Object ordering is not part of the request.
export const OpFields = Schema.Record({ key: Schema.String, value: Schema.Unknown });
export function prepareOp(fields: typeof OpFields.Type) {
	const parsed = Schema.decodeUnknownEither(SentOp, { onExcessProperty: 'error' })(fields);
	if (parsed._tag === 'Left') throw apiError(422, 'invalid_request');
	const hash = createHash('sha256')
		.update(
			JSON.stringify(
				Object.fromEntries(
					Object.keys(fields)
						.sort()
						.map((k) => [k, fields[k]])
				)
			)
		)
		.digest('hex');
	const op = parsed.right;
	return {
		op:
			op.type === 'item.restore'
				? {
						...op,
						completed_at: timestamp(op.completed_at, 6),
						added_at: timestamp(op.added_at, 3)
					}
				: op,
		hash
	};
}
type Prepared = ReturnType<typeof prepareOp>;
function apply(scope: Scope, op: Operation, target?: ListRow) {
	// An out-of-scope share target gets a business refusal before any resource checks.
	if (scope.sharedList && !target) return unavailableList();
	switch (op.type) {
		case 'room.rename':
		case 'list.create':
		case 'list.delete':
		case 'list.rename':
			return applyList(scope, op, target);
		case 'item.add':
		case 'item.set_done':
		case 'item.quantity_delta':
		case 'item.edit':
		case 'item.delete':
		case 'item.restore':
			return applyItem(op, target);
		case 'list.tag_add':
		case 'list.tag_remove':
		case 'list.tag_settings':
		case 'list.tag_color':
		case 'list.tag_rename':
		case 'list.visibility':
		case 'item.toggle_tag':
			return applyTagOp(op, target);
	}
}
function answerSeq(scope: Scope) {
	return Effect.gen(function* () {
		const sql = yield* SqliteClient.SqliteClient;
		const list = scope.sharedList;
		const [row] = list
			? yield* sql<{
					seq: number;
				}>`SELECT COALESCE(MAX(seq),0) AS seq FROM (SELECT changed_seq AS seq FROM lists WHERE id=${list.id} UNION ALL SELECT changed_seq FROM items WHERE list_id=${list.id} UNION ALL SELECT changed_seq FROM deletions WHERE list_uid=${list.uid} UNION ALL SELECT changed_seq FROM share_seq_floors WHERE list_uid=${list.uid})`
			: yield* sql<{ seq: number }>`SELECT change_seq AS seq FROM rooms WHERE id=${scope.roomId}`;
		return row.seq;
	});
}

// The caller admits the room or share inside the same write transaction.
// Verify the scope before looking up an answer, including on a retry.
export function submitOpInTransaction(scope: Scope, { op, hash }: Prepared) {
	return Effect.gen(function* () {
		const sql = yield* SqliteClient.SqliteClient;
		const id = uuid(op.op_id);
		if (scope.sharedList) {
			const list = scope.sharedList;
			const [admitted] =
				yield* sql`SELECT 1 FROM lists WHERE id=${list.id} AND uid=${list.uid} AND room_id=${scope.roomId}`;
			if (!admitted) return yield* apiError(401, 'share_unavailable');
			if (!Schema.is(SentShareOp)(op))
				return yield* apiError(422, 'invalid_request', 'A share link cannot do this.');
		}
		const [prior] = yield* sql<{
			room_id: number;
			request_hash: string;
			response_json: string;
		}>`SELECT room_id,request_hash,response_json FROM processed_ops WHERE op_id=${id}`;
		if (prior) {
			const [format, scopeUid, digest] = prior.request_hash.split(':');
			if (
				prior.room_id !== scope.roomId ||
				format !== 'v1' ||
				digest !== hash ||
				(scope.sharedList && scopeUid !== scope.sharedList.uid)
			)
				return yield* apiError(409, 'op_id_reused');
			const answer = Schema.decodeUnknownSync(OpResponse)(JSON.parse(prior.response_json));
			return { answer, replayed: true };
		}
		const target = 'list_uid' in op ? yield* findTarget(scope, op.list_uid) : undefined;
		// A business refusal rolls back the inner savepoint; its answer remains in the outer transaction.
		const outcome = yield* sql.withTransaction(apply(scope, op, target)).pipe(
			Effect.map((result: Result) => ({ status: 'applied' as const, result })),
			Effect.catchTag('Refusal', ({ code, message, item_uid }) =>
				Effect.succeed({
					status: 'rejected' as const,
					code,
					message,
					...(item_uid ? { item_uid } : {})
				})
			)
		);
		const answer: Answer = { op_id: id, seq: yield* answerSeq(scope), ...outcome };
		const fingerprint = `v1:${target?.uid ?? '-'}:${hash}`;
		yield* sql`INSERT INTO processed_ops(op_id,room_id,request_hash,response_json) VALUES (${id},${scope.roomId},${fingerprint},${JSON.stringify(answer)})`;
		return { answer, replayed: false };
	});
}
export function submitRoomOp(slug: string, token: string | null, prepared: Prepared) {
	return Effect.gen(function* () {
		const sql = yield* SqliteClient.SqliteClient;
		const { roomId, result } = yield* sql.withTransaction(
			Effect.gen(function* () {
				const { id } = yield* requireRoomAccess(slug, token);
				return { roomId: id, result: yield* submitOpInTransaction({ roomId: id }, prepared) };
			})
		);
		if (!result.replayed && result.answer.status === 'applied') wakeRoomStreams(roomId);
		return result;
	});
}

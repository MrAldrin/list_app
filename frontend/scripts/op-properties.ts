// Run with Bun. Create a disposable current-schema database; never use caller data.
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
import fc from 'fast-check';
import { Effect, TestClock, TestContext } from 'effect';
import { maintainOpAnswers } from '../src/lib/server/op-retention';
import { SqliteClient } from '@effect/sql-sqlite-bun';
import { prepareOp, submitOpInTransaction } from '../src/lib/server/room-ops';
import type { Scope } from '../src/lib/server/op-domain';
import { runtime } from '../src/lib/server/runtime';

const root = fileURLToPath(new URL('../../', import.meta.url));
const dir = mkdtempSync(join(tmpdir(), 'listr-ops-'));
process.env.DB_PATH = join(dir, 'test.sqlite');
process.env.APP_PASSWORD = 'disposable';
try {
	execFileSync(
		'uv',
		['run', 'python', '-c', 'from database_setup import open_database; open_database()'],
		{ cwd: root, env: { ...process.env, PYTHONPATH: resolve(root, 'src') } }
	);
	const sql = await runtime.runPromise(SqliteClient.SqliteClient);
	const [room] = await runtime.runPromise(sql<{ id: number }>`SELECT id FROM rooms`);
	const scope = { roomId: room.id };
	const run = (op: Record<string, unknown>, s: Scope = scope) =>
		runtime.runPromise(sql.withTransaction(submitOpInTransaction(s, prepareOp(op))));
	const list_uid = crypto.randomUUID();
	const item_uid = crypto.randomUUID();
	const body = (type: string, fields: Record<string, unknown>) => ({
		op_id: crypto.randomUUID(),
		type,
		...fields
	});
	const listCreate = body('list.create', { uid: list_uid, name: 'List' });
	await run(listCreate);
	const [list] = await runtime.runPromise(
		sql<{ id: number; uid: string }>`SELECT id,uid FROM lists WHERE uid=${list_uid}`
	);
	// obligation: entity-fields.OpScope, entity-fields.List, entity-optional.OpScope.shared_list
	const shared = { roomId: room.id, sharedList: list };
	const add = body('item.add', { list_uid, uid: item_uid, name: 'Rice' });
	// obligation: rule-failure.ReplaySameOp.1, rule-failure.RefuseReusedOpId.1
	const first = await run(add);
	// obligation: entity-fields.StoredOpAnswer, entity-optional.StoredOpAnswer.answer_list
	const [record] = await runtime.runPromise(
		sql<{
			room_id: number;
			request_hash: string;
			response_json: string;
		}>`SELECT room_id,request_hash,response_json FROM processed_ops WHERE op_id=${add.op_id}`
	);
	assert.equal(record.room_id, room.id);
	assert.deepEqual(JSON.parse(record.response_json), first.answer);
	assert.equal(record.request_hash, `v1:${list.uid}:${prepareOp(add).hash}`);
	// obligation: rule-failure.FirstOp.1, rule-failure.RefuseReusedOpId.2
	assert.deepEqual((await run(add, shared)).answer, first.answer);
	const secondUid = crypto.randomUUID();
	await run(body('list.create', { uid: secondUid, name: 'Other' }));
	const [second] = await runtime.runPromise(
		sql<{ id: number; uid: string }>`SELECT id,uid FROM lists WHERE uid=${secondUid}`
	);
	await assert.rejects(run(add, { roomId: room.id, sharedList: second }), /op_id|already used/i);
	await assert.rejects(run(listCreate, shared), /share link cannot/i);
	// obligation: invariant.OneRoomPerScope; rule-failure.ReplaySameOp.2
	const [other] = await runtime.runPromise(
		sql<{
			id: number;
		}>`INSERT INTO rooms(name,slug,password_hash) VALUES ('Other','other','unused') RETURNING id`
	);
	await assert.rejects(run(add, { roomId: other.id, sharedList: list }), /share link was reset/i);
	await assert.rejects(run(add, { roomId: other.id }), /op_id|already used/i);
	const absent = body('item.delete', { list_uid: crypto.randomUUID(), item_uid });
	assert.equal((await run(absent)).answer.status, 'rejected');
	await assert.rejects(run(absent, shared), /op_id|already used/i);
	assert.deepEqual(
		await runtime.runPromise(
			sql`SELECT request_hash FROM processed_ops WHERE op_id=${absent.op_id}`
		),
		[{ request_hash: `v1:-:${prepareOp(absent).hash}` }]
	);
	// A transport error, even while storing the answer, commits neither the op nor its effects.
	// obligation: rule-failure.FirstOp.2
	const failed = body('item.quantity_delta', { list_uid, item_uid, delta: 7 });
	await runtime.runPromise(
		sql`CREATE TEMP TRIGGER fail_answer BEFORE INSERT ON processed_ops BEGIN SELECT RAISE(ABORT,'injected storage failure'); END`
	);
	await assert.rejects(run(failed));
	await runtime.runPromise(sql`DROP TRIGGER fail_answer`);
	assert.deepEqual(
		await runtime.runPromise(sql`SELECT quantity FROM items WHERE uid=${item_uid}`),
		[{ quantity: 1 }]
	);
	assert.deepEqual(
		await runtime.runPromise(sql`SELECT op_id FROM processed_ops WHERE op_id=${failed.op_id}`),
		[]
	);
	// Exercise actual SQLite effects, not a second implementation of the handler.
	await fc.assert(
		fc.asyncProperty(
			fc.array(fc.integer({ min: -12, max: 12 }), { minLength: 1, maxLength: 12 }),
			async (deltas) => {
				let quantity = 1;
				await run(
					body('item.edit', {
						list_uid,
						item_uid,
						name: 'Rice',
						description: '',
						quantity,
						base_seq: Number.MAX_SAFE_INTEGER
					})
				);
				for (const delta of deltas) {
					const op = body('item.quantity_delta', { list_uid, item_uid, delta });
					const before = quantity;
					const [previous] = await runtime.runPromise(
						sql<{ changed_seq: number }>`SELECT changed_seq FROM items WHERE uid=${item_uid}`
					);
					const applied = await run(op, shared);
					assert.equal(applied.replayed, false);
					assert.equal(applied.answer.status, 'applied');
					const retry = await run(Object.fromEntries(Object.entries(op).reverse()));
					assert.equal(retry.replayed, true);
					assert.deepEqual(retry.answer, applied.answer);
					quantity = Math.max(1, quantity + delta);
					const [row] = await runtime.runPromise(
						sql<{
							quantity: number;
							changed_seq: number;
						}>`SELECT quantity,changed_seq FROM items WHERE uid=${item_uid}`
					);
					assert.equal(row.quantity, quantity);
					assert.equal(row.changed_seq === previous.changed_seq, quantity === before);
					const edit = body('item.edit', {
						list_uid,
						item_uid,
						name: 'Rice',
						description: '',
						quantity,
						base_seq: 0
					});
					const same = await run(edit);
					assert.equal(same.answer.status, 'applied');
					if (same.answer.status === 'applied')
						assert.equal(same.answer.result.changed_seq, row.changed_seq);
					const stale = await run({ ...edit, op_id: crypto.randomUUID(), quantity: quantity + 1 });
					assert.equal(stale.answer.status, 'rejected');
					if (stale.answer.status === 'rejected')
						assert.equal(stale.answer.code, 'changed_meanwhile');
					const [after] = await runtime.runPromise(
						sql<{
							quantity: number;
							changed_seq: number;
						}>`SELECT quantity,changed_seq FROM items WHERE uid=${item_uid}`
					);
					assert.deepEqual(after, row);
				}
			}
		),
		{ numRuns: 16 }
	);
	// Age one answer after startup. Advancing the Effect clock runs daily pruning without sleeping.
	await runtime.runPromise(
		Effect.scoped(
			Effect.gen(function* () {
				yield* maintainOpAnswers;
				yield* sql`UPDATE processed_ops SET created_at='2000-01-01' WHERE op_id=${absent.op_id}`;
				yield* TestClock.adjust('1 day');
				assert.deepEqual(
					yield* sql`SELECT op_id FROM processed_ops WHERE op_id=${absent.op_id}`,
					[]
				);
				assert.equal(
					(yield* sql`SELECT op_id FROM processed_ops WHERE op_id=${add.op_id}`).length,
					1
				);
			})
		).pipe(Effect.provide(TestContext.TestContext))
	);
	assert.equal((await run(absent)).replayed, false);
	console.log('Operation properties, retention and replay scope passed');
} finally {
	await runtime.dispose();
	rmSync(dir, { recursive: true, force: true });
}

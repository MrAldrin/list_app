import { SqliteClient } from '@effect/sql-sqlite-bun';
import { Effect } from 'effect';
import { itemNameKey } from './op-name-keys';
import { Refusal, textField, uuid, version, type Operation } from './op-domain';
import { cycle, mergeDue, resolveDue, undated } from './op-due';
import { freshUid, unavailableList, type ListRow } from './op-lists';

type ItemRow = {
	id: number;
	uid: string;
	name: string;
	description: string | null;
	quantity: number | null;
	done: number;
	changed_seq: number;
	date: string | null;
	due_time: string | null;
	due_timezone: string | null;
	due_at: string | null;
	due_cycle: string | null;
	due_cycle_started_at: string | null;
};
type ItemOp = Exclude<Extract<Operation, { type: `item.${string}` }>, { type: 'item.toggle_tag' }>;
function reopen(row: ItemRow) {
	return Effect.gen(function* () {
		const sql = yield* SqliteClient.SqliteClient;
		const c = cycle(row.date);
		yield* sql`UPDATE items SET done=0,completed_at=NULL,add_count=add_count+1,added_at=${new Date().toISOString()},due_cycle=${c.id},due_cycle_started_at=${c.start} WHERE id=${row.id}`;
	});
}
function changed(uid: string) {
	return Effect.gen(function* () {
		const sql = yield* SqliteClient.SqliteClient;
		const [row] = yield* sql<{
			changed_seq: number;
		}>`SELECT changed_seq FROM items WHERE uid=${uid}`;
		return { changed_seq: row.changed_seq };
	});
}
export function applyItem(op: ItemOp, target?: ListRow) {
	return Effect.gen(function* () {
		const sql = yield* SqliteClient.SqliteClient;
		const uid = 'uid' in op ? yield* freshUid(op.uid) : undefined;
		if (!target) return yield* unavailableList();
		if (op.type === 'item.add' || op.type === 'item.restore') {
			const id = uid ?? crypto.randomUUID();
			const name = yield* textField(op.name, 'Name');
			const key = itemNameKey(name);
			const [match] =
				yield* sql<ItemRow>`SELECT * FROM items WHERE list_id=${target.id} AND name_key=${key}`;
			if (match) {
				if (op.type === 'item.restore')
					return yield* new Refusal({
						code: 'undo_name_taken',
						message: 'Cannot undo: item name already exists'
					});
				if (!match.done)
					return yield* new Refusal({
						code: 'duplicate_active',
						message: `'${name}' is already on the list`,
						item_uid: match.uid
					});
				yield* reopen(match);
				return {
					item_uid: match.uid,
					outcome: 'restored' as const,
					...(yield* changed(match.uid))
				};
			}
			const [count] = yield* sql<{
				n: number;
			}>`SELECT COUNT(*) AS n FROM items WHERE list_id=${target.id}`;
			if (count.n >= 1000)
				return yield* new Refusal({
					code: 'too_many',
					message: 'A list can have at most 1000 items'
				});
			if (op.type === 'item.add') {
				yield* sql`INSERT INTO items(name,name_key,done,list_id,uid,added_at) VALUES (${name},${key},0,${target.id},${id},${new Date().toISOString()})`;
				return { item_uid: id, outcome: 'added' as const, ...(yield* changed(id)) };
			}
			const due = yield* mergeDue(undated, op);
			const at = yield* resolveDue(due);
			const c = cycle(due.date);
			const desc = yield* textField(op.description, 'Description', false);
			yield* sql`INSERT INTO items(name,name_key,done,list_id,active_tags,description,quantity,completed_at,uid,date,due_time,due_timezone,due_at,due_cycle,due_cycle_started_at,add_count,added_at) VALUES (${name},${key},${Number(op.done)},${target.id},${JSON.stringify(op.tags)},${desc},${Math.max(1, op.quantity)},${op.done ? op.completed_at : null},${id},${due.date},${due.due_time},${due.due_timezone},${at},${c.id},${c.start},${op.add_count ?? 1},${op.added_at ?? null})`;
			return { item_uid: id, ...(yield* changed(id)) };
		}
		const id = uuid(op.item_uid);
		if (op.type === 'item.delete') {
			yield* sql`DELETE FROM items WHERE list_id=${target.id} AND uid=${id}`;
			return {};
		}
		const [row] = yield* sql<ItemRow>`SELECT * FROM items WHERE list_id=${target.id} AND uid=${id}`;
		if (!row)
			return yield* new Refusal({
				code: 'item_not_found',
				message: 'The item is no longer available.'
			});
		if (op.type === 'item.set_done') {
			const same = Boolean(row.done) === op.done;
			yield* version(op.base_seq, row.changed_seq, same);
			if (!same) {
				if (op.done)
					yield* sql`UPDATE items SET done=1,completed_at=${Temporal.Now.instant().toString({ fractionalSecondDigits: 6 })} WHERE id=${row.id}`;
				else yield* reopen(row);
			}
		} else if (op.type === 'item.quantity_delta') {
			const quantity = Math.max(1, (row.quantity ?? 1) + op.delta);
			if (row.quantity !== quantity)
				yield* sql`UPDATE items SET quantity=${quantity} WHERE id=${row.id}`;
		} else if (op.type === 'item.edit') {
			const name = yield* textField(op.name, 'Name');
			const desc = yield* textField(op.description, 'Description');
			const quantity = op.quantity == null ? row.quantity : Math.max(1, op.quantity);
			const due = yield* mergeDue(row, op);
			const scheduleChanged =
				due.date !== row.date ||
				due.due_time !== row.due_time ||
				due.due_timezone !== row.due_timezone;
			const same =
				name === row.name &&
				desc === (row.description ?? '') &&
				quantity === row.quantity &&
				!scheduleChanged;
			yield* version(op.base_seq, row.changed_seq, same);
			if (!same) {
				const at = scheduleChanged ? yield* resolveDue(due) : row.due_at;
				const c = scheduleChanged
					? cycle(due.date)
					: { id: row.due_cycle, start: row.due_cycle_started_at };
				const key = itemNameKey(name);
				const clash =
					yield* sql`SELECT id FROM items WHERE list_id=${target.id} AND id!=${row.id} AND name_key=${key}`;
				if (clash.length)
					return yield* new Refusal({
						code: 'duplicate_name',
						message: `'${name}' already exists`
					});
				yield* sql`UPDATE items SET name=${name},name_key=${key},description=${desc},quantity=${quantity},date=${due.date},due_time=${due.due_time},due_timezone=${due.due_timezone},due_at=${at},due_cycle=${c.id},due_cycle_started_at=${c.start} WHERE id=${row.id}`;
			}
		}
		return yield* changed(id);
	});
}

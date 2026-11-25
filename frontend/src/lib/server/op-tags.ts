import { SqliteClient } from '@effect/sql-sqlite-bun';
import { Effect } from 'effect';
import { sortTags } from '#lib/data/order.ts';
import { Refusal, textField, uuid, type Operation } from './op-domain';
import { unavailableList, type ListRow } from './op-lists';

type TagOp = Extract<
	Operation,
	{ type: `list.tag_${string}` | 'item.toggle_tag' | 'list.visibility' }
>;
type Options = {
	list_tags: string | null;
	tag_colors: string | null;
	tag_mode: 'single' | 'multi';
	tag_show_on_items: number;
	tag_only_item_tags: number;
	hide_done_mode: 'off' | 'all' | 'age' | 'recent';
	hide_done_age_days: number;
	hide_done_recent_count: number;
};
type ItemTags = { id: number; active_tags: string | null };

function storedJson(raw: string | null): unknown {
	try {
		return raw === null ? null : (JSON.parse(raw) as unknown);
	} catch {
		return null;
	}
}
function tags(raw: string | null): string[] {
	const value = storedJson(raw);
	return Array.isArray(value) ? value.filter((tag) => typeof tag === 'string') : [];
}
function colors(raw: string | null): Map<string, number> {
	const value = storedJson(raw);
	return new Map(
		value && typeof value === 'object' && !Array.isArray(value)
			? Object.entries(value as Record<string, unknown>).filter(
					(entry): entry is [string, number] =>
						typeof entry[1] === 'number' &&
						Number.isInteger(entry[1]) &&
						entry[1] >= 0 &&
						entry[1] <= 6
				)
			: []
	);
}
function unknownTag() {
	return new Refusal({ code: 'unknown_tag', message: 'The tag is not on this list.' });
}
function updateItemTags(item: ItemTags, next: string[]) {
	return Effect.gen(function* () {
		const sql = yield* SqliteClient.SqliteClient;
		yield* sql`UPDATE items SET active_tags=${JSON.stringify(next)} WHERE id=${item.id}`;
	});
}
function withoutTag(old: string[], tag: string): string[] {
	return old.includes(tag) ? old.filter((name) => name !== tag) : old;
}

function mapItemTags(listId: number, change: (old: string[]) => string[]) {
	return Effect.gen(function* () {
		const sql = yield* SqliteClient.SqliteClient;
		const rows = yield* sql<ItemTags>`SELECT id,active_tags FROM items WHERE list_id=${listId}`;
		for (const row of rows) {
			const old = tags(row.active_tags);
			const next = change(old);
			if (next !== old) yield* updateItemTags(row, next);
		}
	});
}

export function applyTagOp(op: TagOp, target?: ListRow) {
	return Effect.gen(function* () {
		if (!target) return yield* unavailableList();
		const sql = yield* SqliteClient.SqliteClient;
		const id = target.id;
		const [stored] =
			yield* sql<Options>`SELECT list_tags,tag_colors,tag_mode,tag_show_on_items,tag_only_item_tags,hide_done_mode,hide_done_age_days,hide_done_recent_count FROM lists WHERE id=${id}`;
		const names = tags(stored.list_tags);
		switch (op.type) {
			case 'item.toggle_tag': {
				const [item] = yield* sql<
					ItemTags & { changed_seq: number }
				>`SELECT id,active_tags,changed_seq FROM items WHERE list_id=${id} AND uid=${uuid(op.item_uid)}`;
				if (!item)
					return yield* new Refusal({
						code: 'item_not_found',
						message: 'The item is no longer available.'
					});
				const old = tags(item.active_tags);
				const present = old.includes(op.tag);
				const active = op.active ?? !present;
				let next = old;
				if (!active && present) next = old.filter((name) => name !== op.tag);
				if (active && stored.tag_mode === 'single' && (!present || old.length !== 1))
					next = [op.tag];
				if (active && stored.tag_mode === 'multi' && !present) next = [...old, op.tag];
				if (next === old) return { changed_seq: item.changed_seq };
				yield* updateItemTags(item, next);
				const [row] = yield* sql<{
					changed_seq: number;
				}>`SELECT changed_seq FROM items WHERE id=${item.id}`;
				return { changed_seq: row.changed_seq };
			}
			case 'list.tag_add': {
				const name = yield* textField(op.tag, 'Tag');
				if (names.includes(name)) break;
				if (names.length >= 50)
					return yield* new Refusal({
						code: 'too_many',
						message: 'A list can have at most 50 tags'
					});
				yield* sql`UPDATE lists SET list_tags=${JSON.stringify(sortTags([...names, name]))} WHERE id=${id}`;
				// A new tag starts empty, even after a pre-port deletion left hidden assignments.
				yield* mapItemTags(id, (old) => withoutTag(old, name));
				break;
			}
			case 'list.tag_remove': {
				if (!names.includes(op.tag)) break;
				const palette = colors(stored.tag_colors);
				palette.delete(op.tag);
				yield* sql`UPDATE lists SET list_tags=${JSON.stringify(names.filter((name) => name !== op.tag))},tag_colors=${JSON.stringify(Object.fromEntries(palette))} WHERE id=${id}`;
				yield* mapItemTags(id, (old) => withoutTag(old, op.tag));
				break;
			}
			case 'list.tag_rename': {
				const name = yield* textField(op.new_tag, 'Tag');
				if (!names.includes(op.tag)) return yield* unknownTag();
				if (name === op.tag) break;
				if (names.includes(name))
					return yield* new Refusal({
						code: 'duplicate_name',
						message: `'${name}' already exists`
					});
				const palette = colors(stored.tag_colors);
				const color = palette.get(op.tag);
				if (color !== undefined) {
					palette.delete(op.tag);
					palette.set(name, color);
				}
				const renamed = sortTags(names.map((tag) => (tag === op.tag ? name : tag)));
				yield* sql`UPDATE lists SET list_tags=${JSON.stringify(renamed)},tag_colors=${JSON.stringify(Object.fromEntries(palette))} WHERE id=${id}`;
				yield* mapItemTags(id, (old) =>
					old.includes(op.tag) ? [...new Set(old.map((tag) => (tag === op.tag ? name : tag)))] : old
				);
				break;
			}
			case 'list.tag_color': {
				if (!names.includes(op.tag)) return yield* unknownTag();
				const palette = colors(stored.tag_colors);
				if ((palette.get(op.tag) ?? null) === op.color) break;
				if (op.color === null) palette.delete(op.tag);
				else palette.set(op.tag, op.color);
				yield* sql`UPDATE lists SET tag_colors=${JSON.stringify(Object.fromEntries(palette))} WHERE id=${id}`;
				break;
			}
			case 'list.tag_settings': {
				const mode = op.mode ?? stored.tag_mode;
				const show =
					op.show_on_items === undefined ? stored.tag_show_on_items : Number(op.show_on_items);
				const only =
					op.only_item_tags === undefined ? stored.tag_only_item_tags : Number(op.only_item_tags);
				if (
					mode === stored.tag_mode &&
					show === stored.tag_show_on_items &&
					only === stored.tag_only_item_tags
				)
					break;
				yield* sql`UPDATE lists SET tag_mode=${mode},tag_show_on_items=${show},tag_only_item_tags=${only} WHERE id=${id}`;
				if (mode === 'single' && stored.tag_mode !== 'single') {
					const order = new Map(names.map((name, index) => [name, index]));
					const rank = (tag: string) => order.get(tag) ?? names.length;
					yield* mapItemTags(id, (old) =>
						old.length < 2
							? old
							: [old.reduce((first, tag) => (rank(tag) < rank(first) ? tag : first))]
					);
				}
				break;
			}
			case 'list.visibility': {
				const mode = op.mode ?? stored.hide_done_mode;
				const age = op.age_days ?? stored.hide_done_age_days;
				const count = op.recent_count ?? stored.hide_done_recent_count;
				if (
					mode === stored.hide_done_mode &&
					age === stored.hide_done_age_days &&
					count === stored.hide_done_recent_count
				)
					break;
				yield* sql`UPDATE lists SET hide_done_mode=${mode},hide_done_age_days=${age},hide_done_recent_count=${count} WHERE id=${id}`;
				break;
			}
		}
		const [row] = yield* sql<{ changed_seq: number }>`SELECT changed_seq FROM lists WHERE id=${id}`;
		return { changed_seq: row.changed_seq };
	});
}

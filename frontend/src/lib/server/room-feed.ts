import { SqliteClient } from '@effect/sql-sqlite-bun';
import { Effect, Schema } from 'effect';
import {
	TagColor,
	type Deletion,
	type Item,
	type List,
	type RoomFeed
} from '#lib/contracts/v1/feed.ts';
import { sortTags } from '#lib/data/order.ts';
import { apiError } from './api';
import { timestamp } from './op-domain';
import { requireRoomAccess } from './room-access';

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

const isTagColor = Schema.is(TagColor);
function colors(raw: string | null): Record<string, number> {
	const value = storedJson(raw);
	return value && typeof value === 'object' && !Array.isArray(value)
		? Object.fromEntries(Object.entries(value).filter(([, color]) => isTagColor(color)))
		: {};
}

function completedAt(done: boolean, stored: string | null): string | null {
	if (!done) return null;
	try {
		return timestamp(stored, 6);
	} catch {
		return null;
	}
}

type ListRow = Pick<typeof List.Type, 'uid' | 'slug' | 'name' | 'changed_seq'> & {
	list_tags: string | null;
	hide_done_mode: typeof List.Type.hide_done.mode;
	hide_done_age_days: number;
	hide_done_recent_count: number;
	tag_mode: typeof List.Type.tag_settings.mode;
	tag_show_on_items: number;
	tag_only_item_tags: number;
	tag_colors: string | null;
};

type ItemRow = Omit<
	typeof Item.Type,
	'done' | 'quantity' | 'description' | 'tags' | 'add_count'
> & {
	done: number | null;
	quantity: number | null;
	description: string | null;
	active_tags: string | null;
	add_count: number | null;
};

// Use -1 for a full snapshot: rows from before change tracking can have seq 0.
// A share read can also restrict these queries to its authorized list.
export function readFeedLists(roomId: number, after = -1, listId?: number) {
	return Effect.gen(function* () {
		const sql = yield* SqliteClient.SqliteClient;
		const rows = yield* sql<ListRow>`
			SELECT uid, slug, name, changed_seq, list_tags,
			       hide_done_mode, hide_done_age_days, hide_done_recent_count,
			       tag_mode, tag_show_on_items, tag_only_item_tags, tag_colors
			FROM lists WHERE room_id = ${roomId} AND changed_seq > ${after}
			${listId === undefined ? sql`` : sql`AND id = ${listId}`}
			ORDER BY id
		`;
		return rows.map((row): typeof List.Type => ({
			uid: row.uid,
			slug: row.slug,
			name: row.name,
			changed_seq: row.changed_seq,
			tags: sortTags(tags(row.list_tags)),
			hide_done: {
				mode: row.hide_done_mode,
				age_days: row.hide_done_age_days,
				recent_count: row.hide_done_recent_count
			},
			tag_settings: {
				mode: row.tag_mode,
				show_on_items: Boolean(row.tag_show_on_items),
				only_item_tags: Boolean(row.tag_only_item_tags),
				colors: colors(row.tag_colors)
			}
		}));
	});
}

export function readFeedItems(roomId: number, after = -1, listId?: number) {
	return Effect.gen(function* () {
		const sql = yield* SqliteClient.SqliteClient;
		const rows = yield* sql<ItemRow>`
			SELECT i.uid, l.uid AS list_uid, i.name, i.done, i.completed_at, i.quantity,
			       i.description, i.active_tags, i.changed_seq, i.date, i.add_count, i.added_at,
			       i.due_time, i.due_timezone, i.due_at
			FROM items AS i JOIN lists AS l ON l.id = i.list_id
			WHERE l.room_id = ${roomId} AND i.changed_seq > ${after}
			${listId === undefined ? sql`` : sql`AND l.id = ${listId}`}
			ORDER BY i.id
		`;
		return rows.map(
			({
				active_tags,
				done,
				quantity,
				description,
				completed_at,
				add_count,
				...row
			}): typeof Item.Type => ({
				...row,
				done: Boolean(done),
				completed_at: completedAt(Boolean(done), completed_at),
				quantity: quantity ?? 1,
				description: description ?? '',
				tags: tags(active_tags),
				add_count: add_count ?? 1
			})
		);
	});
}

export function readRoomFeed(roomSlug: string, token: string | null, since: bigint) {
	return Effect.gen(function* () {
		if (token === null) return yield* apiError(401, 'not_authenticated');
		const sql = yield* SqliteClient.SqliteClient;
		// Access, the cursor and all rows must describe the same SQLite snapshot.
		return yield* sql.withTransaction(
			Effect.gen(function* () {
				const { id, slug, name } = yield* requireRoomAccess(roomSlug, token);
				const [{ seq, floor }] = yield* sql<{ seq: number; floor: number }>`
					SELECT change_seq AS seq, deletions_pruned_seq AS floor FROM rooms WHERE id = ${id}
				`;
				const full = since === 0n || since > seq || since < floor;
				const after = full ? -1 : Number(since);
				const lists = yield* readFeedLists(id, after);
				const items = yield* readFeedItems(id, after);
				const deletions = full
					? []
					: yield* sql<typeof Deletion.Type>`
					SELECT kind, uid FROM deletions WHERE room_id = ${id} AND changed_seq > ${after}
					ORDER BY changed_seq, id
				`;
				return {
					seq,
					full,
					room: { slug, name },
					lists,
					items,
					deletions: [...deletions]
				} satisfies typeof RoomFeed.Type;
			})
		);
	});
}

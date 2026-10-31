// Applying one changes feed to the server state of a room (docs/api.md, "Reading").

import type { RoomData } from './overlay';
import type { Feed } from './types';

/** A full feed replaces everything; a delta upserts by `uid` and removes deletions. */
export function mergeFeed(server: RoomData, feed: Feed): RoomData {
	const lists = new Map(feed.full ? [] : server.lists);
	const items = new Map(feed.full ? [] : server.items);
	const groups = new Map(feed.full ? [] : server.groups);
	for (const list of feed.lists) lists.set(list.uid, list);
	for (const item of feed.items) items.set(item.uid, item);
	for (const group of feed.groups) groups.set(group.uid, group);

	const deletedLists = new Set<string>();
	for (const deletion of feed.deletions) {
		if (deletion.kind === 'list') {
			lists.delete(deletion.uid);
			deletedLists.add(deletion.uid);
		} else if (deletion.kind === 'item') {
			items.delete(deletion.uid);
		} else {
			groups.delete(deletion.uid);
		}
	}
	// A deleted list takes its items with it, listed in the feed or not.
	if (deletedLists.size > 0) {
		for (const [uid, item] of items) {
			if (deletedLists.has(item.list_uid)) items.delete(uid);
		}
	}
	return { lists, items, groups };
}

// Applying one changes feed to the server state of a room (docs/api.md, "Reading").

import type { RoomData } from './overlay';
import type { Feed } from './types';

/** A full feed replaces everything; a delta upserts by `uid` and removes deletions. */
export function mergeFeed(server: RoomData, feed: Feed): RoomData {
	const lists = new Map(feed.full ? [] : server.lists);
	const items = new Map(feed.full ? [] : server.items);
	for (const list of feed.lists) lists.set(list.uid, list);
	for (const item of feed.items) items.set(item.uid, item);

	const deletedLists = new Set<string>();
	for (const deletion of feed.deletions) {
		if (deletion.kind === 'list') {
			lists.delete(deletion.uid);
			deletedLists.add(deletion.uid);
		} else {
			items.delete(deletion.uid);
		}
	}
	// A deleted list takes its items with it, listed in the feed or not.
	if (deletedLists.size > 0) {
		for (const [uid, item] of items) {
			if (deletedLists.has(item.list_uid)) items.delete(uid);
		}
	}
	return { lists, items };
}

import { Schema } from 'effect';
import { ClockTime, Day, EmptyJson, Room, Seq, Uid } from './common';

export const HideDoneMode = Schema.Literal('off', 'all', 'age', 'recent');
export const HideDoneCount = Schema.Int.pipe(Schema.between(1, 100_000));
export const HideDone = Schema.mutable(
	Schema.Struct({ mode: HideDoneMode, age_days: HideDoneCount, recent_count: HideDoneCount })
);
export const TagMode = Schema.Literal('single', 'multi');
export const TagColor = Schema.Int.pipe(Schema.between(0, 6));
export const TagSettings = Schema.mutable(
	Schema.Struct({
		mode: TagMode,
		show_on_items: Schema.Boolean,
		only_item_tags: Schema.Boolean,
		colors: Schema.mutable(Schema.Record({ key: Schema.String, value: TagColor }))
	})
);
export const Tags = Schema.mutable(Schema.Array(Schema.String));
export const AddCount = Schema.Int.pipe(Schema.positive());

export const List = Schema.Struct({
	uid: Uid,
	// Empty in a share feed: this slug is room navigation.
	slug: Schema.String,
	name: Schema.String,
	tags: Tags,
	hide_done: HideDone,
	tag_settings: TagSettings,
	changed_seq: Seq
});
export const Item = Schema.Struct({
	uid: Uid,
	list_uid: Uid,
	name: Schema.String,
	done: Schema.Boolean,
	completed_at: Schema.NullOr(Schema.String),
	quantity: Schema.Int.pipe(Schema.positive()),
	description: Schema.String,
	date: Schema.NullOr(Day),
	due_time: Schema.NullOr(ClockTime),
	due_timezone: Schema.NullOr(Schema.String),
	// Confirmed by the server; never part of an op request.
	due_at: Schema.NullOr(Schema.String),
	tags: Tags,
	add_count: AddCount,
	added_at: Schema.NullOr(Schema.String),
	changed_seq: Seq
}).pipe(Schema.mutable);
export const Deletion = Schema.Struct({ kind: Schema.Literal('list', 'item'), uid: Uid });

const FeedFields = {
	seq: Seq,
	items: Schema.mutable(Schema.Array(Item))
};
export const RoomFeed = Schema.Struct({
	...FeedFields,
	full: Schema.Boolean,
	room: Room,
	lists: Schema.mutable(Schema.Array(List)),
	deletions: Schema.mutable(Schema.Array(Deletion))
});
export const ShareFeed = Schema.Struct({
	...FeedFields,
	full: Schema.Literal(true),
	room: Schema.NullOr(Room),
	lists: Schema.mutable(Schema.Array(Schema.Struct({ ...List.fields, slug: Schema.Literal('') }))),
	deletions: Schema.mutable(Schema.Tuple())
});

// The frontend uses one common type for the two feeds and for local test data.
export const Feed = Schema.Struct({ ...RoomFeed.fields, room: Schema.NullOr(Room) }).pipe(
	Schema.mutable
);

// SSE data is JSON. The comment frame has no event name or JSON payload.
export const EventFrame = Schema.Union(
	Schema.Struct({ event: Schema.Literal('seq'), data: Schema.Struct({ seq: Seq }) }),
	Schema.Struct({ event: Schema.Literal('revoked'), data: EmptyJson }),
	Schema.Struct({ comment: Schema.Literal('ping') })
);

import { Schema } from 'effect';
import { REJECTION_CODES } from './codes';
import { ClockTime, Day, RequestUid, Seq, Uid } from './common';
import { AddCount, HideDoneCount, HideDoneMode, TagColor, TagMode, Tags } from './feed';

// Only use this for optional fields where the API treats null like omission.
const optionalSetting = <S extends Schema.Schema.Any>(schema: S) =>
	Schema.optionalWith(schema, { nullable: true });
const Quantity = Schema.Int.pipe(Schema.between(-1_000_000, 1_000_000));
const listTarget = { list_uid: RequestUid };
const itemTarget = { ...listTarget, item_uid: RequestUid };
const clientUid = { uid: optionalSetting(RequestUid) };
const dueFields = {
	date: Schema.optional(Schema.NullOr(Day)),
	due_time: Schema.optional(Schema.NullOr(ClockTime)),
	due_timezone: Schema.optional(Schema.NullOr(Schema.String.pipe(Schema.maxLength(64))))
};

export const RoomRenameOp = Schema.Struct({
	type: Schema.Literal('room.rename'),
	name: Schema.String
});
export const ListCreateOp = Schema.Struct({
	type: Schema.Literal('list.create'),
	name: Schema.String,
	...clientUid
});
export const ListRenameOp = Schema.Struct({
	type: Schema.Literal('list.rename'),
	...listTarget,
	name: Schema.String,
	base_seq: Seq
});
export const ListDeleteOp = Schema.Struct({ type: Schema.Literal('list.delete'), ...listTarget });
export const ListTagAddOp = Schema.Struct({
	type: Schema.Literal('list.tag_add'),
	...listTarget,
	tag: Schema.String
});
export const ListTagRemoveOp = Schema.Struct({
	type: Schema.Literal('list.tag_remove'),
	...listTarget,
	tag: Schema.String
});
export const ListTagSettingsOp = Schema.Struct({
	type: Schema.Literal('list.tag_settings'),
	...listTarget,
	mode: optionalSetting(TagMode),
	show_on_items: optionalSetting(Schema.Boolean),
	only_item_tags: optionalSetting(Schema.Boolean)
}).pipe(
	Schema.filter(
		(op) =>
			op.mode !== undefined || op.show_on_items !== undefined || op.only_item_tags !== undefined,
		{
			message: () => 'Send at least one tag setting'
		}
	)
);
export const ListTagColorOp = Schema.Struct({
	type: Schema.Literal('list.tag_color'),
	...listTarget,
	tag: Schema.String,
	color: Schema.NullOr(TagColor)
});
export const ListTagRenameOp = Schema.Struct({
	type: Schema.Literal('list.tag_rename'),
	...listTarget,
	tag: Schema.String,
	new_tag: Schema.String
});
export const ListVisibilityOp = Schema.Struct({
	type: Schema.Literal('list.visibility'),
	...listTarget,
	mode: optionalSetting(HideDoneMode),
	age_days: optionalSetting(HideDoneCount),
	recent_count: optionalSetting(HideDoneCount)
}).pipe(
	Schema.filter(
		(op) => op.mode !== undefined || op.age_days !== undefined || op.recent_count !== undefined,
		{
			message: () => 'Send at least one visibility setting'
		}
	)
);
export const ItemAddOp = Schema.Struct({
	type: Schema.Literal('item.add'),
	...listTarget,
	...clientUid,
	name: Schema.String
});
export const ItemSetDoneOp = Schema.Struct({
	type: Schema.Literal('item.set_done'),
	...itemTarget,
	done: Schema.Boolean,
	base_seq: optionalSetting(Seq)
});
export const ItemQuantityDeltaOp = Schema.Struct({
	type: Schema.Literal('item.quantity_delta'),
	...itemTarget,
	delta: Quantity
});
export const ItemEditOp = Schema.Struct({
	type: Schema.Literal('item.edit'),
	...itemTarget,
	name: Schema.String,
	description: Schema.String,
	quantity: Schema.optional(Schema.NullOr(Quantity)),
	...dueFields,
	base_seq: Seq
});
export const ItemToggleTagOp = Schema.Struct({
	type: Schema.Literal('item.toggle_tag'),
	...itemTarget,
	tag: Schema.String,
	active: optionalSetting(Schema.Boolean)
});
export const ItemDeleteOp = Schema.Struct({ type: Schema.Literal('item.delete'), ...itemTarget });
export const ItemRestoreOp = Schema.Struct({
	type: Schema.Literal('item.restore'),
	...listTarget,
	...clientUid,
	name: Schema.String,
	done: Schema.Boolean,
	tags: Tags,
	description: Schema.String,
	quantity: Quantity,
	completed_at: Schema.NullOr(Schema.String),
	...dueFields,
	add_count: optionalSetting(AddCount),
	added_at: Schema.optional(Schema.NullOr(Schema.String))
});

const ShareOp = Schema.Union(
	ListTagAddOp,
	ListTagRemoveOp,
	ListTagSettingsOp,
	ListTagColorOp,
	ListTagRenameOp,
	ListVisibilityOp,
	ItemAddOp,
	ItemSetDoneOp,
	ItemQuantityDeltaOp,
	ItemEditOp,
	ItemToggleTagOp,
	ItemDeleteOp,
	ItemRestoreOp
);
export const Op = Schema.Union(
	RoomRenameOp,
	ListCreateOp,
	ListRenameOp,
	ListDeleteOp,
	...ShareOp.members
);
const OpId = Schema.Struct({ op_id: RequestUid });
export const SentOp = Schema.extend(Op, OpId).pipe(Schema.mutable);
export const SentShareOp = Schema.extend(ShareOp, OpId);

export const ListCreateResult = Schema.Struct({
	list_uid: Uid,
	slug: Schema.String,
	created: Schema.Boolean
});
export const ItemRestoreResult = Schema.Struct({
	item_uid: Uid,
	// Replays stored before changed_seq was added do not have this field.
	changed_seq: Schema.optional(Seq)
});
export const ItemAddResult = Schema.Struct({
	...ItemRestoreResult.fields,
	outcome: Schema.Literal('added', 'restored')
});

// The response does not echo the operation type. A few operations return {},
// and old one-row replays may also have no changed_seq.
const AppliedResult = Schema.Struct({
	item_uid: Schema.optional(ItemAddResult.fields.item_uid),
	outcome: Schema.optional(ItemAddResult.fields.outcome),
	changed_seq: ItemAddResult.fields.changed_seq,
	list_uid: Schema.optional(ListCreateResult.fields.list_uid),
	slug: Schema.optional(ListCreateResult.fields.slug),
	created: Schema.optional(ListCreateResult.fields.created)
}).pipe(
	Schema.filter((result) => {
		if (
			result.list_uid !== undefined ||
			result.slug !== undefined ||
			result.created !== undefined
		) {
			return (
				result.list_uid !== undefined &&
				result.slug !== undefined &&
				result.created !== undefined &&
				result.item_uid === undefined &&
				result.outcome === undefined &&
				result.changed_seq === undefined
			);
		}
		return result.outcome === undefined || result.item_uid !== undefined;
	})
);
export const RejectionCode = Schema.Literal(...REJECTION_CODES);
const AnswerFields = { op_id: Uid, seq: Seq };
export const OpApplied = Schema.Struct({
	...AnswerFields,
	status: Schema.Literal('applied'),
	result: AppliedResult
});
export const OpRejected = Schema.Struct({
	...AnswerFields,
	status: Schema.Literal('rejected'),
	code: RejectionCode,
	message: Schema.String,
	item_uid: Schema.optional(Uid)
}).pipe(
	Schema.filter(
		(answer) => (answer.code === 'duplicate_active') === (answer.item_uid !== undefined)
	)
);
export const OpResponse = Schema.Union(OpApplied, OpRejected);

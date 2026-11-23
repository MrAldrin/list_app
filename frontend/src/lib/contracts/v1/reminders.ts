import { Schema } from 'effect';
import { ClockTime, Day, RequestUid, Seq, Uid, ZoneName } from './common';

export const Mode = Schema.Literal('quiet', 'daily_summary', 'scheduled', 'custom');
const ContentPrivacy = Schema.Literal('generic', 'counts', 'names');
const Revision = Schema.Int.pipe(Schema.positive());
const DailyCap = Schema.Int.pipe(Schema.between(1, 50));
const SpacingMinutes = Schema.Int.pipe(Schema.between(1, 60));
const OverdueRepeatDays = Schema.Int.pipe(Schema.between(1, 30));
const QuietHours = Schema.Struct({ start: ClockTime, end: ClockTime }).pipe(
	Schema.filter(({ start, end }) => start !== end, {
		message: () => 'Use different start and end times'
	})
);

const EnrollmentFields = { mode: Mode, summary_time: ClockTime };
const ExistingEnrollment = Schema.Struct({
	state: Schema.Literal('active', 'needs_resume', 'opted_out'),
	revision: Revision,
	...EnrollmentFields,
	activated_at: Schema.NullOr(Schema.String)
});
export const Enrollment = Schema.Union(
	Schema.Struct({ state: Schema.Literal('not_enrolled'), revision: Schema.Null }),
	ExistingEnrollment
);
export const EnrollmentResponse = Schema.Struct({ enrollment: Enrollment });
export const EnrollmentWriteResponse = Schema.Struct({ enrollment: ExistingEnrollment });
export const EnrollBody = Schema.Struct({
	op_id: RequestUid,
	base_revision: Schema.optional(Schema.NullOr(Revision)),
	timezone: Schema.optional(Schema.NullOr(ZoneName)),
	mode: Schema.optional(Schema.NullOr(Mode)),
	summary_time: Schema.optional(Schema.NullOr(ClockTime))
});
export const EnrollmentPatchBody = Schema.Struct({
	op_id: RequestUid,
	base_revision: Revision,
	mode: Schema.optional(Schema.NullOr(Mode)),
	summary_time: Schema.optional(Schema.NullOr(ClockTime)),
	opted_out: Schema.optional(Schema.NullOr(Schema.Literal(true)))
});

const DeviceSettings = Schema.Struct({
	timezone: ZoneName,
	all_day_time: ClockTime,
	paused: Schema.Boolean,
	quiet_hours: Schema.NullOr(QuietHours),
	daily_cap: DailyCap,
	spacing_minutes: SpacingMinutes,
	content_privacy: ContentPrivacy,
	overdue_repeat_days: Schema.NullOr(OverdueRepeatDays)
});
export const Device = Schema.Struct({ ...DeviceSettings.fields, revision: Revision });
export const DeviceResponse = Schema.Struct({ device: Schema.NullOr(Device) });
export const DeviceWriteResponse = Schema.Struct({ device: Device });
export const DevicePatchBody = Schema.extend(
	Schema.Struct({ op_id: RequestUid, base_revision: Revision }),
	Schema.partial(DeviceSettings)
);

export const PolicyScope = Schema.Literal('room', 'list', 'item');
const PolicyState = Schema.Literal('inherit', 'off', 'replace');
const RelativeLimits = { minutes: 525_600, hours: 8_760, days: 365, weeks: 52 } as const;
const WallFields = { date: Day, time: ClockTime, timezone: ZoneName };
export const InputRule = Schema.Union(
	Schema.Struct({
		kind: Schema.Literal('relative'),
		amount: Schema.NonNegativeInt,
		unit: Schema.Literal('minutes', 'hours', 'days', 'weeks')
	}).pipe(Schema.filter(({ amount, unit }) => amount <= RelativeLimits[unit])),
	Schema.Struct({ kind: Schema.Literal('fixed'), id: Schema.optional(Uid), ...WallFields })
);
export const StoredRule = Schema.Union(
	Schema.Struct({
		kind: Schema.Literal('relative'),
		basis: Schema.Literal('at_due', 'elapsed', 'calendar'),
		amount: Schema.NonNegativeInt,
		key: Schema.String
	}),
	Schema.Struct({
		kind: Schema.Literal('fixed'),
		id: Uid,
		...WallFields,
		instant: Schema.String,
		activation: Schema.String
	})
);
export const Policy = Schema.Struct({
	scope: PolicyScope,
	state: PolicyState,
	preset: Schema.NullOr(Mode),
	summary_enabled: Schema.Boolean,
	rules: Schema.mutable(Schema.Array(StoredRule)).pipe(Schema.maxItems(5)),
	revision: Seq,
	activated_at: Schema.NullOr(Schema.String)
});
export const PolicyResponse = Schema.Struct({ policy: Policy, effective: Policy });
const DraftFields = {
	state: PolicyState,
	preset: Schema.optional(Schema.NullOr(Mode)),
	rules: Schema.optional(Schema.Array(InputRule).pipe(Schema.maxItems(5))),
	summary_enabled: Schema.optional(Schema.Boolean)
};
export const PolicyBody = Schema.Struct({
	...DraftFields,
	op_id: RequestUid,
	base_revision: Seq,
	// Legacy requests may send null here. Only the room takes a time value.
	summary_time: Schema.optional(Schema.Null)
});
export const RoomPolicyBody = Schema.Struct({
	...PolicyBody.fields,
	state: Schema.Literal('replace'),
	summary_time: Schema.optional(Schema.NullOr(ClockTime))
});
export const PreviewBody = Schema.Struct({
	item_uid: Schema.optional(Schema.NullOr(RequestUid)),
	item_id: Schema.optional(Schema.NullOr(Schema.Int.pipe(Schema.positive()))),
	draft: Schema.optional(Schema.NullOr(Schema.Struct(DraftFields)))
}).pipe(
	Schema.filter(({ item_uid, item_id }) => (item_uid != null) !== (item_id != null), {
		message: () => 'Provide exactly one item identifier'
	})
);
export const Preview = Schema.Struct({
	source: PolicyScope,
	state: PolicyState,
	preset: Schema.NullOr(Mode),
	timezone: Schema.String,
	disabled_reasons: Schema.mutable(Schema.Array(Schema.String)),
	provisional_fixed_ids: Schema.mutable(Schema.Array(Uid)),
	entries: Schema.mutable(
		Schema.Array(
			Schema.Struct({
				kind: Schema.Literal('rules', 'summary'),
				instant: Schema.String,
				keys: Schema.mutable(Schema.Array(Schema.String)),
				deferred_until: Schema.NullOr(Schema.String),
				local_day: Schema.NullOr(Day)
			})
		)
	).pipe(Schema.maxItems(5))
});

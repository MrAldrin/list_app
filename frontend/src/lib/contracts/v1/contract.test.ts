import { Schema } from 'effect';
import { describe, expect, it } from 'vitest';
import { isActionCode } from '../../data/result';
import { ErrorResponse } from './common';
import { EventFrame } from './feed';
import { OpResponse } from './ops';
import { API_V1 } from './routes';

const id = 'aabbccdd-1122-3344-5566-778899001122';
const strict = { onExcessProperty: 'error' } as const;

const roomOp = Schema.decodeUnknownSync(API_V1['POST /rooms/{slug}/ops'].body, strict);
const shareOp = Schema.decodeUnknownSync(API_V1['POST /share/{token}/ops'].body, strict);
const response = Schema.decodeUnknownSync(OpResponse, strict);

const edit = {
	type: 'item.edit',
	op_id: id,
	list_uid: id,
	item_uid: id,
	base_seq: 0,
	name: 'Tea',
	description: ''
};

describe('API v1 contract', () => {
	it('keeps an absent due field distinct from a null that clears it', () => {
		expect(roomOp(edit)).not.toHaveProperty('due_time');
		expect(roomOp({ ...edit, due_time: null })).toHaveProperty('due_time', null);
		expect(() => roomOp({ ...edit, due_at: '2026-11-23T11:00:00Z' })).toThrow();
		expect(() => roomOp({ ...edit, date: '2026-02-29' })).toThrow();
		expect(() => roomOp({ ...edit, base_seq: '0' })).toThrow();
	});

	it('accepts older optional fields but requires at least one setting', () => {
		const settings = { type: 'list.tag_settings', op_id: id, list_uid: id, mode: null };
		expect(roomOp({ ...settings, show_on_items: false })).toHaveProperty('show_on_items', false);
		expect(() => roomOp(settings)).toThrow();
	});

	it('limits share writes to operations inside the list', () => {
		expect(shareOp(edit)).toEqual(edit);
		const rename = { type: 'list.rename', op_id: id, list_uid: id, base_seq: 0, name: 'New' };
		expect(roomOp(rename)).toEqual(rename);
		expect(() => shareOp(rename)).toThrow();
	});

	it('reads stored applied answers with no changed_seq', () => {
		const replay = {
			op_id: id,
			seq: 2,
			status: 'applied',
			result: { item_uid: id, outcome: 'restored' }
		};
		expect(response(replay)).toEqual(replay);
		expect(() => response({ ...replay, result: { outcome: 'restored' } })).toThrow();
	});

	it.each(['invalid_due', 'time_zone_unavailable'])('recognizes the %s rejection', (code) => {
		const rejected = { op_id: id, seq: 2, status: 'rejected', code, message: 'Check the time.' };
		expect(response(rejected)).toEqual(rejected);
		expect(isActionCode(code)).toBe(true);
		expect(() => response({ ...rejected, code: 'not_authenticated' })).toThrow();
	});

	it('keeps HTTP errors separate from op rejections and SSE events', () => {
		const error = Schema.decodeUnknownSync(ErrorResponse, strict);
		const frame = Schema.decodeUnknownSync(EventFrame, strict);
		expect(error({ error: { code: 'not_authenticated', message: 'Sign in.' } })).toBeDefined();
		expect(() => error({ error: { code: 'invalid_due', message: 'Check the time.' } })).toThrow();
		expect(frame({ event: 'seq', data: { seq: 2 } })).toBeDefined();
		expect(frame({ event: 'revoked', data: {} })).toBeDefined();
		expect(frame({ comment: 'ping' })).toBeDefined();
		expect(() => frame({ event: 'revoked', data: { seq: 2 } })).toThrow();
	});

	it('separates reminder request data from server fields', () => {
		const device = Schema.decodeUnknownSync(
			API_V1['PATCH /rooms/{slug}/reminders/preferences/device'].body,
			strict
		);
		const patch = { op_id: id, base_revision: 1, quiet_hours: null };
		expect(device(patch)).toEqual(patch);
		expect(() => device({ ...patch, paused: null })).toThrow();
		const preview = Schema.decodeUnknownSync(
			API_V1['POST /rooms/{slug}/reminders/preview'].body,
			strict
		);
		expect(preview({ item_uid: id, draft: null })).toBeDefined();
		expect(() => preview({ item_uid: id, item_id: 7 })).toThrow();
		expect(() => preview({ item_uid: id, draft: { state: 'replace', due_at: null } })).toThrow();
	});
});

import { describe, expect, it } from 'vitest';
import { formatUtc, invitationUrl, statusLabel } from './invitations';

describe('invitation texts', () => {
	it('shows UTC times as NiceGUI does', () => {
		expect(formatUtc('1970-01-08T00:00:00Z')).toBe('1970-01-08 00:00 UTC');
		expect(formatUtc('2026-10-05T09:12:44Z')).toBe('2026-10-05 09:12 UTC');
		expect(formatUtc('odd')).toBe('odd');
	});

	it('capitalises the status', () => {
		expect(statusLabel('active')).toBe('Active');
		expect(statusLabel('revoked')).toBe('Revoked');
		expect(statusLabel('expired')).toBe('Expired');
	});

	it('builds the full link from the path alone', () => {
		expect(invitationUrl('a-b_c', 'https://lists.example')).toBe(
			'https://lists.example/create-room/a-b_c'
		);
	});
});

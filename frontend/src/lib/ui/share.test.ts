import { describe, expect, it, vi } from 'vitest';
import { absoluteUrl, copyText, shareMessage, shareNatively } from './share';

describe('share helpers', () => {
	it('uses NiceGUI texts', () => {
		expect(shareMessage('list')).toBe('Anyone with this link can open this list.');
		expect(shareMessage('room')).toBe('The recipient will also need the room password.');
	});

	it('builds the full address from the path only', () => {
		expect(absoluteUrl('/share/abc', 'https://lists.example')).toBe(
			'https://lists.example/share/abc'
		);
	});

	it('opens the share sheet with only the URL for clean iPhone copying', async () => {
		const share = vi.fn(async () => undefined);
		expect(await shareNatively('https://x/share/t', { share })).toBe('shared');
		expect(share).toHaveBeenCalledWith({
			url: 'https://x/share/t'
		});
	});

	it('falls back to the dialog without a share sheet or when it fails', async () => {
		expect(await shareNatively('https://x', {})).toBe('fallback');
		const broken = vi.fn(async () => {
			throw new DOMException('not allowed', 'NotAllowedError');
		});
		expect(await shareNatively('https://x', { share: broken })).toBe('fallback');
	});

	it('does nothing more when the user closes the share sheet', async () => {
		const cancelled = vi.fn(async () => {
			throw new DOMException('cancelled', 'AbortError');
		});
		expect(await shareNatively('https://x', { share: cancelled })).toBe('cancelled');
	});

	it('copies with the clipboard API, and reports when it cannot', async () => {
		const writeText = vi.fn(async () => undefined);
		expect(await copyText('link', undefined, { writeText })).toBe(true);
		expect(writeText).toHaveBeenCalledWith('link');

		const denied = vi.fn(async () => {
			throw new DOMException('denied', 'NotAllowedError');
		});
		expect(await copyText('link', undefined, { writeText: denied })).toBe(false);
		expect(await copyText('link', undefined, undefined)).toBe(false);
	});
});

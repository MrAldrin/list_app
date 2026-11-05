import type { RoomHandle } from '#lib/data/index.ts';
import { ReminderApi } from './api';

class ZoneState {
	value = $state<string | undefined>();
	generation = 0;
	lifetime = 0;
}
const zones = new WeakMap<RoomHandle, ZoneState>();
function state(room: RoomHandle): ZoneState {
	let value = zones.get(room);
	if (!value) {
		value = new ZoneState();
		zones.set(room, value);
	}
	return value;
}
export function deviceZone(room: RoomHandle): string | undefined {
	return state(room).value;
}
export function setDeviceZone(room: RoomHandle, zone: string | undefined): void {
	const entry = state(room);
	entry.generation++;
	entry.value = zone;
}
/** Only an active room grant permits the private device zone to influence this view. */
export function loadDeviceZone(room: RoomHandle): () => void {
	const entry = state(room);
	const generation = ++entry.generation;
	const lifetime = ++entry.lifetime;
	entry.value = undefined;
	const api = new ReminderApi(room.slug);
	void (async () => {
		try {
			const enrollment = await api.enrollment();
			if (enrollment.enrollment.state !== 'active') return;
			const device = await api.device();
			if (entry.generation === generation) entry.value = device.device?.timezone;
		} catch {
			/* A private read is optional; use the browser zone. */
		}
	})();
	return () => {
		if (entry.lifetime === lifetime) {
			entry.lifetime++;
			entry.generation++;
			entry.value = undefined;
		}
	};
}

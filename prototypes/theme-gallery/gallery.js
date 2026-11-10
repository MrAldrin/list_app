/* Static, local-only gallery. All preview directions share this synthetic data and interaction layer. */
const DRAFTS = [
	{ id: 'reference', level: 0, name: 'Current reference', style: 'Classic baseline', concept: 'The current ListR arrangement: centered room list, compact top bar, one-line item rows, tags, and bottom add bar.', seam: 'Reference baseline — copied as a static prototype; no live app code or data.' },
	{ id: 'porcelain-ink', level: 1, name: 'Porcelain Ink', style: 'Near-neutral', concept: 'Almost-black ink on soft porcelain. A quiet palette lets item text carry the hierarchy.', seam: 'Palette-only: same reference DOM, geometry, spacing, shapes, labels, and control positions.' },
	{ id: 'citrus-grove', level: 1, name: 'Citrus Grove', style: 'Cream + forest', concept: 'Warm paper and forest green make a bright, grounded palette without moving a single control.', seam: 'Palette-only: same reference DOM and geometry; only color values differ.' },
	{ id: 'marine-signal', level: 1, name: 'Marine Signal', style: 'Cyan + navy', concept: 'Cool pale-cyan surfaces and deep navy text give the exact layout a crisp, coastal feel.', seam: 'Palette-only: same reference DOM and geometry; only color values differ.' },
	{ id: 'aubergine', level: 1, name: 'Aubergine', style: 'Lilac + plum', concept: 'Lilac surfaces and plum accents provide a softer, more personal mood with no layout change.', seam: 'Palette-only: same reference DOM and geometry; only color values differ.' },
	{ id: 'ember-clay', level: 1, name: 'Ember Clay', style: 'Sand + rust', concept: 'Sand, cream, and dark rust bring warmth while every reference element stays put.', seam: 'Palette-only: same reference DOM and geometry; only color values differ.' },
	{ id: 'market', level: 2, name: 'Market', style: 'Friendly cards', concept: 'Soft green surfaces, softer input corners, and gentle card shadows make list scanning feel warm and welcoming.', seam: 'Component styling: rounded surfaces, button shapes, type scale, borders, and spacing; familiar placements stay.' },
	{ id: 'editorial', level: 2, name: 'Editorial', style: 'Serif + rules', concept: 'A serif list title, small caps, and hairline dividers bring a printed-shopping-list character.', seam: 'Component styling: typography and rules change; familiar header, rows, controls, and bottom add position stay.' },
	{ id: 'utility', level: 2, name: 'Utility', style: 'Square + precise', concept: 'Squared edges, firm dividers, and compact numerical labels prioritize quick scanning.', seam: 'Component styling: density, borders, and control treatment change; familiar placements stay.' },
	{ id: 'cushion', level: 2, name: 'Cushion', style: 'Soft touch', concept: 'More generous item rows, a pill-shaped add field, and a quiet warm background feel calm on a phone.', seam: 'Component styling: rounded forms, spacing, and typography change; room/list organization stays.' },
	{ id: 'ledger', level: 2, name: 'Ledger', style: 'Ruled + tabular', concept: 'Tabular quantities, restrained amber highlights, and ledger-like row rules make details easy to compare.', seam: 'Component styling: font, numeric rhythm, line work, and accent change; familiar placements stay.' },
	{ id: 'index-rail', level: 3, name: 'Index Rail', style: 'Persistent list index', concept: 'A vertical list index sits beside the active items so list-to-list movement is immediate. It navigates lists inside this room, not between rooms.', seam: 'Layout work: a list-navigation rail replaces the single centered column. Persistent navigation is a prototype assumption, not an app decision.' },
	{ id: 'category-atlas', level: 3, name: 'Category Atlas', style: 'Tag-led sections', concept: 'Items are divided under tag headings, with a clear untagged section. Grouping uses the first displayed tag only; every item still shows all of its tags.', seam: 'Layout work: display-only tag grouping; it does not create categories or change tag/filter rules.' },
	{ id: 'today-ledger', level: 3, name: 'Today Ledger', style: 'Due-date timeline', concept: 'Dated items appear in date sections and undated items stay in a separate section. Checked items remain visible in their date group.', seam: 'Layout work: display-only date grouping. It suggests no reminder, sorting, or due-date product rule.' },
	{ id: 'split-sheet', level: 3, name: 'Split Sheet', style: 'Index + working pane', concept: 'The working sheet comes first, with a room inventory beside it on wide layouts and below it on phones. Unlike Index Rail, navigation does not precede or squeeze the work.', seam: 'Layout work: work-first sheet plus room-summary cards. This is a prototype composition, not a new room or item rule.' },
	{ id: 'card-mosaic', level: 3, name: 'Card Mosaic', style: 'Metadata cards', concept: 'Each item is a small card with its due date, quantity, tags, and completion status visible together.', seam: 'Layout work: item cards replace rows. No extra workflow states or card actions are assumed.' },
	{ id: 'field-notes', level: 4, name: 'Field Notes', style: 'Notebook spread', concept: 'A ruled paper page, margin marks, and hand-drawn-style dividers make a familiar list feel like a pocket notebook.', seam: 'Interaction/layout experiment: a notebook metaphor in the prototype only; the data and list actions remain ordinary.' },
	{ id: 'dispatch-board', level: 4, name: 'Dispatch Board', style: 'Open / done columns', concept: 'Open and checked items occupy separate columns, making completion state spatial as well as textual.', seam: 'Interaction/layout experiment: columns reflect only the existing checked flag. They do not add workflow states.' },
	{ id: 'focus-deck', level: 4, name: 'Focus Deck', style: 'One task in focus', concept: 'The first open item gets a large, readable stage; the complete item index stays below so nothing disappears.', seam: 'Interaction/layout experiment: a display emphasis only. It adds no prioritization or task-order rule.' },
	{ id: 'terminal', level: 4, name: 'Terminal', style: 'Command console', concept: 'A high-contrast console treatment numbers each item and puts its metadata in a compact second line.', seam: 'Interaction/style experiment: terminal presentation only; real command parsing and keyboard shortcuts are not implied.' },
	{ id: 'orbit-map', level: 4, name: 'Orbit Map', style: 'Spatial room map', concept: 'Room lists form a small constellation of original geometric nodes; the selected list remains a plain, linear, accessible checklist.', seam: 'Interaction/layout experiment: spatial list navigation is prototype-only. It does not imply a persistent room switcher.' }
];

const LEVELS = [
	{ id: 1, title: '01 · Color only', sub: 'Five palette directions. Every preview shares the reference structure and geometry.' },
	{ id: 2, title: '02 · Traditional restyling', sub: 'Five familiar arrangements with a different typographic or component personality.' },
	{ id: 3, title: '03 · Broader redesign', sub: 'Five new compositions while keeping recognizable list tasks.' },
	{ id: 4, title: '04 · Unrestricted experiments', sub: 'Five original metaphors. Assumptions stay inside this local prototype.' }
];

const LISTS = [
	{ id: 'weekly', name: 'Weekly shop', tint: 'leaf', items: [
		{ id: 'bananas', name: 'Ripe bananas', notes: 'Choose a small bunch; green tips are fine.', quantity: 6, tags: ['Produce'], due: '2026-11-06', done: false },
		{ id: 'oat-milk', name: 'Barista oat milk', notes: 'The unsweetened carton with the blue cap.', quantity: 2, tags: ['Chilled', 'Pantry'], due: '2026-11-06', due_time: '17:00', due_timezone: 'Europe/Oslo', done: false },
		{ id: 'olive-oil', name: 'Extra-virgin olive oil', notes: 'Medium bottle for everyday cooking.', quantity: 1, tags: ['Pantry'], due: '2026-11-08', done: false },
		{ id: 'batteries', name: 'AA batteries for the hallway sensor', notes: 'Check the drawer before buying; we may have a spare pack.', quantity: 2, tags: ['Home'], due: '2026-11-04', due_time: '09:00', due_timezone: 'Europe/Oslo', done: false },
		{ id: 'coffee-filters', name: 'Coffee filters', notes: '', quantity: 1, tags: ['Pantry'], due: '', done: true },
		{ id: 'tiny-yogurt', name: 'Tiny-batch raspberry yogurt', notes: 'The individual cups, not the large tub.', quantity: 4, tags: ['Chilled'], due: '', done: true },
		{ id: 'dish-soap', name: 'Dish soap', notes: '', quantity: 1, tags: ['Home'], due: '', done: false }
	] },
	{ id: 'cabin', name: 'Weekend cabin restock', tint: 'sky', items: [
		{ id: 'kindling', name: 'Dry kindling and long fireplace matches', notes: 'Store in the covered box by the woodshed.', quantity: 3, tags: ['Cabin', 'Outdoor'], due: '2026-11-07', done: false },
		{ id: 'coffee-beans', name: 'Whole-bean coffee', notes: 'Medium roast for the grinder.', quantity: 1, tags: ['Pantry'], due: '2026-11-08', done: false },
		{ id: 'sheets', name: 'Fresh sheets for the upstairs bunk room', notes: 'Two single sets, cotton if available.', quantity: 2, tags: ['Cabin'], due: '', done: false },
		{ id: 'lantern', name: 'Rechargeable lantern', notes: '', quantity: 1, tags: ['Outdoor'], due: '', done: true }
	] },
	{ id: 'garden', name: 'Garden & greenhouse · spring reset', tint: 'gold', items: [
		{ id: 'compost', name: 'Seed-starting compost', notes: 'Fine-texture mix for the small trays.', quantity: 2, tags: ['Garden'], due: '2026-11-10', done: false },
		{ id: 'twine', name: 'Soft garden twine', notes: '', quantity: 1, tags: ['Garden', 'Tools'], due: '', done: false },
		{ id: 'gloves', name: 'Waterproof gloves for pruning roses', notes: 'Measure hand size first; the last pair pinched.', quantity: 1, tags: ['Tools'], due: '2026-11-12', done: true }
	] },
	{ id: 'first-aid', name: 'First-aid kit', tint: 'rose', items: [
		{ id: 'bandages', name: 'Assorted fabric bandages', notes: 'Include a few larger dressings.', quantity: 2, tags: ['Health'], due: '2026-11-06', done: false },
		{ id: 'saline', name: 'Sterile saline pods', notes: '', quantity: 1, tags: ['Health'], due: '', done: false },
		{ id: 'pain-relief', name: 'Children’s pain relief — check expiry', notes: 'Ask the pharmacist if the box date is unclear.', quantity: 1, tags: ['Health'], due: '2026-11-09', done: true }
	] }
];

const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character]);
const allDrafts = DRAFTS.filter((draft) => draft.level > 0);
let selectedDrafts = new Set();
let activeFilters = new Set();
let editing = null;
/** Draft id prefix for add-input ids; the same list appears in several comparison columns. */
let addInputPrefix = '';
function addInputId(list) { return `add-${addInputPrefix}${list.id}`; }

function routeState() {
	const params = new URLSearchParams(location.search);
	const compare = (params.get('compare') || '').split(',').filter((id) => DRAFTS.some((draft) => draft.id === id && draft.level > 0));
	const draft = DRAFTS.find((item) => item.id === params.get('draft'));
	return {
		draft: draft?.id || '',
		compare: [...new Set(compare)].slice(0, 4),
		mode: params.get('mode') === 'dark' ? 'dark' : 'light',
		view: params.get('view') === 'room' ? 'room' : 'list',
		listId: LISTS.some((list) => list.id === params.get('list')) ? params.get('list') : LISTS[0].id
	};
}

function setRoute(patch, replace = false) {
	const url = new URL(location.href);
	const current = routeState();
	const next = { ...current, ...patch };
	if (patch.listId && patch.listId !== current.listId) activeFilters.clear();
	if (next.draft) url.searchParams.set('draft', next.draft); else url.searchParams.delete('draft');
	if (next.compare?.length) url.searchParams.set('compare', next.compare.join(',')); else url.searchParams.delete('compare');
	url.searchParams.set('mode', next.mode);
	url.searchParams.set('view', next.view);
	if (next.listId) url.searchParams.set('list', next.listId); else url.searchParams.delete('list');
	history[replace ? 'replaceState' : 'pushState']({}, '', url);
	render();
}

function byId(listId) { return LISTS.find((list) => list.id === listId) || LISTS[0]; }
function listSummary(list) {
	const open = list.items.filter((item) => !item.done).length;
	const due = list.items.filter((item) => item.due && !item.done).length;
	return { open, due };
}
function dateLabel(value) {
	if (!value) return '';
	const match = /^([0-9]{4})-([0-9]{2})-([0-9]{2})$/.exec(value);
	if (!match) return value;
	const date = new Date(`${value}T12:00:00`);
	return date.toLocaleDateString('en', { month: 'short', day: 'numeric' });
}
function dueStatus(value) {
	if (!value) return '';
	if (value < '2026-11-06') return 'Overdue';
	if (value === '2026-11-06') return 'Today';
	if (value === '2026-11-07') return 'Tomorrow';
	return '';
}
function dueDisplay(item) {
	if (!item.due) return '';
	const status = dueStatus(item.due);
	return `${status ? `${status} · ` : ''}${dateLabel(item.due)}${item.due_time ? ` · ${item.due_time}` : ''}`;
}
function tagMarkup(tags) {
	return tags.map((tag, index) => `<span class="tag tag-${index % 4}">${esc(tag)}</span>`).join('');
}
function listTags(list) {
	return [...new Set(list.items.flatMap((item) => item.tags))].sort((a, b) => a.localeCompare(b));
}
function referenceItem(item, list, index = 0) {
	const tags = item.tags;
	const letter = (tag) => {
		const first = tag.trim().charAt(0).toLocaleUpperCase();
		return esc(first || '?');
	};
	const status = dueStatus(item.due);
	const due = item.due ? `<span class="ref-date">${esc(dateLabel(item.due))}</span>${status ? `<span class="ref-due ${status === 'Overdue' ? 'danger' : status === 'Today' ? 'warning' : ''}">${esc(status)}</span>` : ''}${item.due_time ? `<span class="ref-time">${esc(item.due_time)}</span>` : ''}` : '';
	const notes = item.notes ? `<span class="ref-note-mark" title="${esc(item.notes)}" aria-label="Has notes">${sourceIcon('note')}</span>` : '';
	const qty = item.quantity > 1 ? `<span class="ref-quantity">×${esc(item.quantity)}</span>` : '';
	const itemTags = tags.map((tag) => `<button type="button" class="ref-item-tag ${item.tags.includes(tag) ? 'selected' : ''}" data-action="toggle-item-tag" data-list-id="${esc(list.id)}" data-item-id="${esc(item.id)}" data-tag="${esc(tag)}" aria-label="${esc(tag)} tag for ${esc(item.name)}" aria-pressed="${item.tags.includes(tag)}" title="${esc(tag)}"><span>${letter(tag)}</span></button>`).join('');
	return `<div class="ref-item ${item.done ? 'done' : ''}" data-item-id="${esc(item.id)}" data-item-index="${index}">
		<label class="ref-check-target"><input type="checkbox" data-action="check" data-item-id="${esc(item.id)}" aria-label="Mark ${esc(item.name)} ${item.done ? 'to do' : 'done'}" ${item.done ? 'checked' : ''}><span aria-hidden="true" class="ref-check-art"></span></label>
		<button type="button" class="ref-item-name" data-action="edit" data-item-id="${esc(item.id)}" aria-label="Edit ${esc(item.name)}"><span>${esc(item.name)}</span>${notes}${qty}${due}</button>
		<div class="ref-item-tags" aria-label="Tags for ${esc(item.name)}">${itemTags}</div>
	</div>`;
}
function itemMarkup(item, index = 0, variant = '') {
	const due = item.due ? `<span class="due-label"><span class="due-mark" aria-hidden="true">◷</span>${esc(dueDisplay(item))}</span>` : '<span class="due-label">No date</span>';
	const note = item.notes ? `<p class="item-note">${esc(item.notes)}</p>` : '';
	const metadata = `<div class="item-meta"><span class="quantity-label">Quantity <b>×${esc(item.quantity)}</b></span>${due}<span class="item-tags">${tagMarkup(item.tags)}</span></div>`;
	return `<article class="item ${item.done ? 'is-done' : ''} ${variant}" data-item-id="${esc(item.id)}" data-item-index="${index}">
		<label class="check-target"><input type="checkbox" data-action="check" data-item-id="${esc(item.id)}" aria-label="Mark ${esc(item.name)} ${item.done ? 'to do' : 'done'}" ${item.done ? 'checked' : ''}><span aria-hidden="true" class="check-art"></span></label>
		<div class="item-copy"><button type="button" class="item-name" data-action="edit" data-item-id="${esc(item.id)}" aria-label="Edit ${esc(item.name)}">${esc(item.name)}</button>${note}<p class="item-state">${item.done ? 'Done' : 'To do'}</p>${metadata}</div>
		<button type="button" class="edit-item" data-action="edit" data-item-id="${esc(item.id)}" aria-label="Edit ${esc(item.name)}">Edit</button>
	</article>`;
}
function addItemForm(list, extraClass = '') {
	return `<div class="add-dock ${extraClass}"><form class="add-form" data-action="add" data-list-id="${esc(list.id)}"><label class="visually-hidden" for="${esc(addInputId(list))}">Add an item to ${esc(list.name)}</label><input id="${esc(addInputId(list))}" name="item" maxlength="160" placeholder="Add an item…" required autocomplete="off"><button class="add-button" type="submit">Add item</button></form></div>`;
}
function listHeading(list, compact = false) {
	return `<div class="list-heading ${compact ? 'compact' : ''}"><p class="eyebrow">${esc(listSummary(list).open)} open · ${esc(listSummary(list).due)} dated</p><h2>${esc(list.name)}</h2></div>`;
}
function roomListCard(list, layout = '') {
	const summary = listSummary(list);
	return `<button class="room-card ${layout}" type="button" data-action="open-list" data-list-id="${esc(list.id)}"><span class="room-card-kicker">LIST · ${esc(list.items.length)} ITEMS</span><strong>${esc(list.name)}</strong><span class="room-card-meta">${summary.open} open <span aria-hidden="true">·</span> ${summary.due} with dates</span><span class="card-arrow" aria-hidden="true">↗</span></button>`;
}
function roomDirectory(className = '') {
	return `<div class="room-directory ${className}" aria-label="Lists in ${esc('Birch House')}">${LISTS.map((list) => roomListCard(list)).join('')}</div>`;
}
function roomAddButton(extra = '') {
	return `<div class="add-dock ${extra}"><button type="button" class="add-button add-list-button" data-action="new-list">＋ Add new list</button></div>`;
}
function referenceRoomAddButton() {
	return `<div class="ref-bottom-bar"><div class="ref-bottom-inner"><button type="button" class="ref-add-list" data-action="new-list">${sourceIcon('add')}<span>Add New List</span></button></div></div>`;
}
function referenceItems(list) {
	const visible = activeFilters.size === 0
		? list.items
		: list.items.filter((item) => [...activeFilters].every((tag) => item.tags.includes(tag)));
	return `<ul class="ref-items" aria-label="Items">${visible.map((item, index) => `<li>${referenceItem(item, list, index)}</li>`).join('')}</ul>`;
}
function referenceTagStrip(list) {
	const tags = listTags(list);
	if (!tags.length) return '';
	return `<ul class="ref-tag-strip" data-intentional-scroll="tag filters" aria-label="Filter items by tag">${tags.map((tag) => `<li><button type="button" class="ref-tag ${activeFilters.has(tag) ? 'on' : ''}" data-action="filter-tag" data-tag="${esc(tag)}" aria-pressed="${activeFilters.has(tag)}">${esc(tag)}</button></li>`).join('')}${activeFilters.size ? '<li><button type="button" class="ref-tag ref-clear" data-action="clear-tags">Clear</button></li>' : ''}</ul>`;
}
function referenceAddForm(list) {
	return `<div class="ref-bottom-bar"><form class="ref-add-form" data-action="add" data-list-id="${esc(list.id)}"><label class="visually-hidden" for="${esc(addInputId(list))}">Item name</label><input id="${esc(addInputId(list))}" name="item" maxlength="160" placeholder="Add or Search" required autocomplete="off"><button class="ref-add-button" type="submit">Add</button></form></div>`;
}
// Existing app Material Design icon paths; see README for source and license.
function sourceIcon(name) {
	const paths = {
		add: 'M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z',
		back: 'M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z',
		note: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z',
		edit: 'M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z',
		delete: 'M6 19a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z',
		bell: 'M12 22c1.1 0 2-.9 2-2h-4c0 1.1.9 2 2 2zm6-6v-5c0-3.07-1.64-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.63 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2z',
		menu: 'M12 8a2 2 0 1 0 0-4 2 2 0 0 0 0 4zm0 2a2 2 0 1 0 0 4 2 2 0 0 0 0-4zm0 6a2 2 0 1 0 0 4 2 2 0 0 0 0-4z'
	};
	return `<svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true" fill="currentColor"><path d="${paths[name]}"></path></svg>`;
}
function sourceRoomCard(entry) {
	const due = dueSoonCount(entry.items);
	return `<li class="card list-row"><button class="ref-list-link" type="button" data-action="open-list" data-list-id="${esc(entry.id)}" aria-label="Open ${esc(entry.name)}"><span>${esc(entry.name)}</span></button>${due ? `<span class="ref-list-due">${due} due</span>` : ''}<button type="button" class="ref-room-icon" disabled title="Illustrative only — renaming lists is outside this preview" aria-label="Rename ${esc(entry.name)} (illustrative)">${sourceIcon('edit')}</button><button type="button" class="ref-room-icon danger" disabled title="Illustrative only — deleting lists is outside this preview" aria-label="Delete ${esc(entry.name)} (illustrative)">${sourceIcon('delete')}</button></li>`;
}
function dueSoonCount(items) {
	return items.filter((item) => !item.done && item.due && item.due <= '2026-11-07').length;
}
function sourceRoomHeader() {
	const due = dueSoonCount(LISTS.flatMap((entry) => entry.items));
	return `<header class="ref-room-header"><span class="ref-brand" aria-hidden="true">List<b>R</b></span><h1 class="ref-room-heading"><button class="ref-room-switch" type="button" disabled title="Illustrative only — the room switcher is not connected"><span class="ref-room-name">Birch House</span><span aria-hidden="true">⌄</span></button></h1><button class="ref-due-control" type="button" disabled title="Illustrative only — due center is not connected" aria-label="Due items (illustrative)">${sourceIcon('bell')}${due ? `<span class="ref-due-badge">${due}</span>` : ''}</button><button class="ref-room-menu" type="button" disabled title="Illustrative only — room menu is not connected" aria-label="Room menu (illustrative)">${sourceIcon('menu')}</button></header>`;
}
function sourceListHeader(list) {
	const due = dueSoonCount(list.items);
	return `<header class="ref-list-header"><button class="ref-back" type="button" data-action="room" aria-label="Back to room">${sourceIcon('back')}</button><h1 title="${esc(list.name)}">${esc(list.name)}</h1><button class="ref-due-control" type="button" disabled title="Illustrative only — due center is not connected" aria-label="Due items (illustrative)">${sourceIcon('bell')}${due ? `<span class="ref-due-badge">${due}</span>` : ''}</button><button class="ref-options" type="button" disabled title="Illustrative only — Options panel is not connected">Options</button><button class="ref-room-menu" type="button" disabled title="Illustrative only — list menu is not connected" aria-label="List menu (illustrative)">${sourceIcon('menu')}</button></header>`;
}
function sharedReference(draft, view, list) {
	const roomBody = `<main class="ref-page"><div class="ref-page-content">${sourceRoomHeader()}<ul class="ref-list-rows">${LISTS.map(sourceRoomCard).join('')}</ul></div>${referenceRoomAddButton()}</main>`;
	const listBody = `<main class="ref-page"><div class="ref-page-content">${sourceListHeader(list)}${referenceTagStrip(list)}${referenceItems(list)}</div>${referenceAddForm(list)}</main>`;
	return `<article class="prototype ref-app ${draft.level === 2 ? `level-two skin-${draft.id}` : ''}" data-draft-id="${draft.id}" data-freedom="${draft.level}" data-view="${view}" data-mode="${routeState().mode}" aria-label="${esc(draft.name)} ${view} preview"><div class="ref-screen">${view === 'room' ? roomBody : listBody}</div><span class="prototype-credit">Reference layout: main room/list geometry. Search suggestions, menus, due center, and list rename/delete are illustrative; edit is a local mock.</span></article>`;
}
function itemList(list, variant = '') {
	return `<div class="item-list ${variant}">${list.items.map((item, index) => itemMarkup(item, index, variant.includes('terminal') ? 'terminal-item' : '')).join('')}</div>`;
}
function railPreview(draft, view, list) {
	const sidebar = `<aside class="rail-sidebar" data-intentional-scroll="list navigation"><p class="eyebrow">BIRCH HOUSE · LIST INDEX</p><div class="rail-links">${LISTS.map((entry) => `<button type="button" class="rail-link ${entry.id === list.id ? 'selected' : ''}" data-action="open-list" data-list-id="${esc(entry.id)}"><span>${esc(entry.name)}</span><small>${listSummary(entry).open} open</small></button>`).join('')}</div><p class="assumption">Local list navigation<br><b>Not a room switcher</b></p></aside>`;
	const content = view === 'room'
		? `<main class="rail-main"><p class="eyebrow">ROOM INDEX · 4 LISTS</p><h2>Everything at Birch House.</h2><p class="intro-line">Choose a list from the index or from these larger cards.</p>${roomDirectory('rail-directory')}${roomAddButton()}</main>`
		: `<main class="rail-main">${listHeading(list)}<div class="rail-tagline">${tagMarkup(listTags(list))}</div>${itemList(list)}${addItemForm(list)}</main>`;
	return `<article class="prototype composition index-rail skin-index-rail" data-draft-id="${draft.id}" data-freedom="${draft.level}" data-view="${view}" data-mode="${routeState().mode}"><header class="composition-top"><span class="brand-small">ListR <i>· Birch House</i></span><span>LIST INDEX</span></header><div class="rail-layout">${sidebar}${content}</div></article>`;
}
function groupedByTag(list) {
	const groups = new Map();
	for (const item of list.items) {
		const heading = item.tags[0] || 'Without a tag';
		if (!groups.has(heading)) groups.set(heading, []);
		groups.get(heading).push(item);
	}
	return [...groups.entries()].map(([heading, items]) => `<section class="atlas-group"><h3><span class="atlas-symbol" aria-hidden="true">✳</span>${esc(heading)} <small>${items.length} items</small></h3>${items.map((item, index) => itemMarkup(item, index, 'atlas-item')).join('')}</section>`).join('');
}
function atlas(draft, view, list) {
	const content = view === 'room'
		? `<main class="atlas-main"><div class="atlas-title"><p class="eyebrow">THE HOUSE INDEX</p><h2>Pick your next aisle.</h2><p>Each card is a list, not a new category.</p></div>${roomDirectory('atlas-directory')}${roomAddButton()}</main>`
		: `<main class="atlas-main"><div class="atlas-title"><p class="eyebrow">TAG ATLAS · DISPLAY GROUPS ONLY</p><h2>${esc(list.name)}</h2><p>Grouped by each item’s first tag; all tags remain on the item.</p></div><div class="atlas-groups">${groupedByTag(list)}</div>${addItemForm(list)}</main>`;
	return `<article class="prototype composition category-atlas skin-category-atlas" data-draft-id="${draft.id}" data-freedom="${draft.level}" data-view="${view}" data-mode="${routeState().mode}"><header class="atlas-header"><span class="atlas-mark" aria-hidden="true">A</span><span><b>Birch House</b><small>THE COMMON ROOM</small></span><span class="atlas-edition">FIELD INDEX · 01</span></header>${content}</article>`;
}
function dueGroup(item) {
	return item.due ? dueDisplay(item) : 'No date';
}
function todayLedger(draft, view, list) {
	const groups = new Map();
	// Prototype display order only; do not mutate the shared sample or app rules.
	const datedFirst = [...list.items].sort((left, right) => (left.due || '9999-12-31').localeCompare(right.due || '9999-12-31'));
	for (const item of datedFirst) {
		const key = dueGroup(item);
		if (!groups.has(key)) groups.set(key, []);
		groups.get(key).push(item);
	}
	const timeline = [...groups.entries()].map(([name, items]) => `<section class="timeline-group"><div class="timeline-date"><span class="timeline-dot" aria-hidden="true"></span><h3>${esc(name)}</h3><span>${items.length} item${items.length === 1 ? '' : 's'}</span></div>${items.map((item, index) => itemMarkup(item, index, 'timeline-item')).join('')}</section>`).join('');
	const content = view === 'room'
		? `<main class="today-main"><p class="eyebrow">BIRCH HOUSE · THE DATEBOOK</p><h2>Lists with a next step.</h2><p class="intro-line">Dates are a display cue, not a reminder.</p><div class="datebook-lists">${LISTS.map((entry) => `<button class="datebook-row" type="button" data-action="open-list" data-list-id="${esc(entry.id)}"><span class="datebook-icon">${listSummary(entry).due.toString().padStart(2, '0')}</span><span><b>${esc(entry.name)}</b><small>${listSummary(entry).open} open · ${listSummary(entry).due} dated</small></span><span aria-hidden="true">→</span></button>`).join('')}</div>${roomAddButton()}</main>`
		: `<main class="today-main"><p class="eyebrow">DATEBOOK · BIRCH HOUSE</p><h2>${esc(list.name)}</h2><p class="intro-line">Dated items are grouped first; nothing is hidden.</p><div class="timeline">${timeline}</div>${addItemForm(list)}</main>`;
	return `<article class="prototype composition today-ledger skin-today-ledger" data-draft-id="${draft.id}" data-freedom="${draft.level}" data-view="${view}" data-mode="${routeState().mode}"><header class="today-header"><span class="today-logo">DAY<br>BOOK</span><div><b>Birch House</b><small>shared lists · date view</small></div><span class="today-count">${view === 'room' ? '04 LISTS' : `${listSummary(list).due} DATED`}</span></header>${content}</article>`;
}
function splitSheet(draft, view, list) {
	const listNav = `<aside class="split-overview" aria-label="Room inventory"><p class="eyebrow">ROOM INVENTORY · BIRCH HOUSE</p><h3>The other sheets</h3><div class="split-summary-grid">${LISTS.map((entry, index) => `<button type="button" class="split-summary-card ${entry.id === list.id ? 'active' : ''}" data-action="open-list" data-list-id="${esc(entry.id)}"><span class="split-number">0${index + 1}</span><b>${esc(entry.name)}</b><small>${entry.id === list.id ? 'Current sheet · ' : ''}${listSummary(entry).open} open · ${listSummary(entry).due} dated</small></button>`).join('')}</div><p class="assumption">Room overview stays below the work on phones. No room switcher is added.</p></aside>`;
	const pane = view === 'room'
		? `<main class="split-work"><p class="eyebrow">ROOM OVERVIEW</p><h2>Choose a sheet.</h2><p class="intro-line">Lists stay in the left index and in this overview.</p><div class="split-cards">${LISTS.map((entry) => roomListCard(entry)).join('')}</div>${roomAddButton()}</main>`
		: `<main class="split-work"><div class="split-work-head"><p class="eyebrow">ACTIVE SHEET</p><p class="sheet-count">${list.items.length} lines</p></div>${listHeading(list)}<div class="split-summary">${listSummary(list).open} still to do <span>·</span> ${listSummary(list).due} dated</div>${itemList(list, 'sheet-items')}${addItemForm(list)}</main>`;
	return `<article class="prototype composition split-sheet skin-split-sheet" data-draft-id="${draft.id}" data-freedom="${draft.level}" data-view="${view}" data-mode="${routeState().mode}"><header class="split-header"><button type="button" data-action="room" class="split-room-link">BIRCH HOUSE</button><span>SHARED PAPERS / 2026</span><span>● LOCAL DEMO</span></header><div class="split-layout">${pane}${view === 'list' ? listNav : ''}</div></article>`;
}
function mosaic(draft, view, list) {
	const cards = list.items.map((item, index) => `<article class="mosaic-item ${item.done ? 'is-done' : ''}" data-item-id="${esc(item.id)}"><div class="mosaic-card-top"><span class="card-number">${String(index + 1).padStart(2, '0')}</span><label class="check-target"><input type="checkbox" data-action="check" data-item-id="${esc(item.id)}" aria-label="Mark ${esc(item.name)} ${item.done ? 'to do' : 'done'}" ${item.done ? 'checked' : ''}><span class="check-art" aria-hidden="true"></span></label></div><button class="mosaic-title" type="button" data-action="edit" data-item-id="${esc(item.id)}">${esc(item.name)}</button>${item.notes ? `<p class="item-note">${esc(item.notes)}</p>` : ''}<div class="mosaic-details"><span class="quantity-label">Quantity <b>${item.quantity}</b></span>${item.due ? `<span class="due-label">${esc(dueDisplay(item))}</span>` : `<span class="due-label">No date</span>`}</div><div class="item-tags">${tagMarkup(item.tags)}</div><span class="mosaic-state">${item.done ? 'DONE' : 'TO DO'}</span></article>`).join('');
	const content = view === 'room'
		? `<main class="mosaic-main"><p class="eyebrow">ROOM COLLECTION · 4 LISTS</p><h2>Birch House shelves</h2><div class="mosaic-room-grid">${LISTS.map((entry) => roomListCard(entry)).join('')}</div>${roomAddButton()}</main>`
		: `<main class="mosaic-main"><div class="mosaic-list-head"><div><p class="eyebrow">ITEM COLLECTION</p><h2>${esc(list.name)}</h2></div><span>${list.items.length} cards</span></div><div class="mosaic-grid">${cards}</div>${addItemForm(list)}</main>`;
	return `<article class="prototype composition card-mosaic skin-card-mosaic" data-draft-id="${draft.id}" data-freedom="${draft.level}" data-view="${view}" data-mode="${routeState().mode}"><header class="mosaic-header"><span class="mosaic-emblem" aria-hidden="true">▦</span><span>THE HOUSE EDIT</span><span>BIRCH HOUSE</span></header>${content}</article>`;
}
function fieldNotes(draft, view, list) {
	const content = view === 'room'
		? `<main class="notes-page"><div class="notes-label">HOUSEHOLD FIELD NOTES · INDEX 04</div><h2>Where the week goes.</h2><p class="notes-deck">A shared pocket notebook. Choose a page to open.</p><div class="notes-index">${LISTS.map((entry, index) => `<button type="button" class="notes-index-row" data-action="open-list" data-list-id="${esc(entry.id)}"><span class="notes-page-no">${String(index + 1).padStart(2, '0')}</span><b>${esc(entry.name)}</b><span>${listSummary(entry).open} open</span></button>`).join('')}</div>${roomAddButton()}</main>`
		: `<main class="notes-page"><button type="button" class="notes-back" data-action="room">← HOUSE INDEX</button><div class="notes-label">PAGE ${String(LISTS.indexOf(list) + 1).padStart(2, '0')} · BIRCH HOUSE</div><h2>${esc(list.name)}</h2><p class="notes-deck">Notes, dates, and quantities stay with each line.</p><div class="notes-rows">${list.items.map((item, index) => `<div class="note-line"><span class="margin-tick">${String(index + 1).padStart(2, '0')}</span>${itemMarkup(item, index, 'notebook-item')}</div>`).join('')}</div>${addItemForm(list)}</main>`;
	return `<article class="prototype composition field-notes skin-field-notes" data-draft-id="${draft.id}" data-freedom="${draft.level}" data-view="${view}" data-mode="${routeState().mode}"><div class="notebook-cover"><span>FIELD NOTES</span><span class="cover-stamp">BH<br>06</span></div><header class="notes-header"><span class="spiral" aria-hidden="true">${'••••••••••••'.split('').join('<br>')}</span><span>BIRCH HOUSE / COMMONPLACE</span><span>VOL. 04</span></header>${content}</article>`;
}
function dispatchBoard(draft, view, list) {
	const open = list.items.filter((item) => !item.done);
	const done = list.items.filter((item) => item.done);
	const lane = (title, items, label) => `<section class="dispatch-lane"><header><span class="lane-lamp ${label}" aria-hidden="true"></span><h3>${title}</h3><span>${items.length}</span></header><div class="dispatch-cards">${items.map((item, index) => `<div class="dispatch-card ${item.done ? 'is-done' : ''}" data-item-id="${esc(item.id)}"><div class="dispatch-card-top"><span>${item.done ? 'CHECKED' : 'OPEN'}</span><label class="check-target"><input type="checkbox" data-action="check" data-item-id="${esc(item.id)}" aria-label="Mark ${esc(item.name)} ${item.done ? 'to do' : 'done'}" ${item.done ? 'checked' : ''}><span class="check-art" aria-hidden="true"></span></label></div><button class="dispatch-title" type="button" data-action="edit" data-item-id="${esc(item.id)}">${esc(item.name)}</button>${item.notes ? `<p class="item-note">${esc(item.notes)}</p>` : ''}<div class="dispatch-meta"><span>× ${item.quantity}</span>${item.due ? `<span>${esc(dueDisplay(item))}</span>` : `<span>No date</span>`}</div><div class="item-tags">${tagMarkup(item.tags)}</div></div>`).join('')}</div></section>`;
	const content = view === 'room'
		? `<main class="dispatch-main"><p class="eyebrow">ROOM ROUTER · BIRCH HOUSE</p><h2>Choose a board.</h2><p class="intro-line">The room index is only a way to open a list.</p><div class="dispatch-room-list">${LISTS.map((entry) => `<button type="button" data-action="open-list" data-list-id="${esc(entry.id)}"><span class="dispatch-marker" aria-hidden="true">▰</span><b>${esc(entry.name)}</b><small>${listSummary(entry).open} open / ${entry.items.length - listSummary(entry).open} checked</small><span>→</span></button>`).join('')}</div>${roomAddButton()}</main>`
		: `<main class="dispatch-main"><div class="dispatch-titlebar"><div><p class="eyebrow">BOARD · BIRCH HOUSE</p><h2>${esc(list.name)}</h2></div><span>Only two states</span></div><div class="dispatch-columns">${lane('In the queue', open, 'open')}${lane('Checked off', done, 'done')}</div>${addItemForm(list)}</main>`;
	return `<article class="prototype composition dispatch-board skin-dispatch-board" data-draft-id="${draft.id}" data-freedom="${draft.level}" data-view="${view}" data-mode="${routeState().mode}"><header class="dispatch-header"><span class="dispatch-signal" aria-hidden="true">●</span><span>HOUSE DISPATCH</span><span>BOARD 04 / LOCAL</span></header>${content}</article>`;
}
function focusDeck(draft, view, list) {
	const spotlight = list.items.find((item) => !item.done) || list.items[0];
	const rest = list.items.filter((item) => item.id !== spotlight?.id);
	const content = view === 'room'
		? `<main class="focus-main"><p class="eyebrow">THE HOUSE / LIST DECK</p><h2>Choose what to open.</h2><div class="focus-room-grid">${LISTS.map((entry, index) => `<button type="button" class="focus-room-card" data-action="open-list" data-list-id="${esc(entry.id)}"><span>DECK ${String(index + 1).padStart(2, '0')}</span><strong>${esc(entry.name)}</strong><small>${listSummary(entry).open} open · ${listSummary(entry).due} dated</small><span aria-hidden="true">↗</span></button>`).join('')}</div>${roomAddButton()}</main>`
		: `<main class="focus-main"><div class="focus-head"><div><p class="eyebrow">CURRENT LIST · ${esc(list.items.length)} ITEMS</p><h2>${esc(list.name)}</h2></div><span class="focus-index">01 / ${String(list.items.length).padStart(2, '0')}</span></div>${spotlight ? `<section class="spotlight"><span class="spotlight-label">ONE OPEN ITEM IN FOCUS</span>${itemMarkup(spotlight, 0, 'spotlight-item')}</section>` : ''}<section class="full-index"><h3>Complete index <span>${list.items.length} items · ${listSummary(list).open} open</span></h3>${rest.map((item, index) => itemMarkup(item, index + 1, 'focus-row')).join('')}</section>${addItemForm(list)}</main>`;
	return `<article class="prototype composition focus-deck skin-focus-deck" data-draft-id="${draft.id}" data-freedom="${draft.level}" data-view="${view}" data-mode="${routeState().mode}"><header class="focus-header"><span class="focus-mark" aria-hidden="true">F</span><span>FOCUS DECK <small>Birch House</small></span><span>FIELD TEST 04</span></header>${content}</article>`;
}
function terminal(draft, view, list) {
	const content = view === 'room'
		? `<main class="terminal-main"><p class="terminal-prompt">$ ls /birch-house/lists</p><h2>Available lists</h2><div class="terminal-listing">${LISTS.map((entry, index) => `<button type="button" data-action="open-list" data-list-id="${esc(entry.id)}"><span>${String(index + 1).padStart(2, '0')}</span><b>${esc(entry.name)}</b><small>${listSummary(entry).open} open · ${listSummary(entry).due} dated</small><i aria-hidden="true">↵</i></button>`).join('')}</div>${roomAddButton()}</main>`
		: `<main class="terminal-main"><p class="terminal-prompt">$ open "${esc(list.name)}"</p><div class="terminal-list-head"><h2>${esc(list.name)}</h2><span>${list.items.length} records</span></div><div class="terminal-lines">${list.items.map((item, index) => `<div class="terminal-row ${item.done ? 'is-done' : ''}" data-item-id="${esc(item.id)}"><span class="line-number">${String(index + 1).padStart(2, '0')}</span><label class="check-target"><input type="checkbox" data-action="check" data-item-id="${esc(item.id)}" aria-label="Mark ${esc(item.name)} ${item.done ? 'to do' : 'done'}" ${item.done ? 'checked' : ''}><span class="check-art" aria-hidden="true"></span></label><div class="terminal-copy"><button type="button" class="terminal-item-name" data-action="edit" data-item-id="${esc(item.id)}">${esc(item.name)}</button><p>${item.done ? 'DONE' : 'TODO'} · QTY ${item.quantity}${item.due ? ` · DUE ${esc(dueDisplay(item).toUpperCase())}` : ' · NO DATE'}</p><div class="item-tags">${tagMarkup(item.tags)}</div>${item.notes ? `<p class="terminal-note">${esc(item.notes)}</p>` : ''}</div></div>`).join('')}</div>${addItemForm(list)}</main>`;
	return `<article class="prototype composition terminal skin-terminal" data-draft-id="${draft.id}" data-freedom="${draft.level}" data-view="${view}" data-mode="${routeState().mode}"><header class="terminal-header"><span><i aria-hidden="true">●</i> LOCAL LIST SHELL</span><span>SESSION: SYNTHETIC</span></header>${content}</article>`;
}
function orbitMap(draft, view, list) {
	const content = view === 'room'
		? `<main class="orbit-main"><div class="orbit-title"><p class="eyebrow">BIRCH HOUSE · LIST CONSTELLATION</p><h2>A small map of shared work.</h2><p>Choose a list node. This map is a prototype navigation idea, not a room switcher.</p></div><div class="orbit-cluster" aria-label="Lists in Birch House">${LISTS.map((entry, index) => `<button type="button" class="orbit-node orbit-${index}" data-action="open-list" data-list-id="${esc(entry.id)}"><span class="orbit-node-number">0${index + 1}</span><b>${esc(entry.name)}</b><small>${listSummary(entry).open} open · ${listSummary(entry).due} dates</small></button>`).join('')}<span class="orbit-center" aria-hidden="true">BIRCH<br>HOUSE</span></div>${roomAddButton()}</main>`
		: `<main class="orbit-main"><div class="orbit-list-head"><button type="button" class="orbit-back" data-action="room">← HOUSE MAP</button><p class="eyebrow">LINEAR ITEM VIEW · ${esc(listSummary(list).open)} TO DO</p><h2>${esc(list.name)}</h2><p>Spatial room navigation; a familiar linear list for the work.</p></div><div class="orbit-item-list">${list.items.map((item, index) => itemMarkup(item, index, 'orbit-item')).join('')}</div>${addItemForm(list)}</main>`;
	return `<article class="prototype composition orbit-map skin-orbit-map" data-draft-id="${draft.id}" data-freedom="${draft.level}" data-view="${view}" data-mode="${routeState().mode}"><header class="orbit-header"><span class="orbit-glyph" aria-hidden="true">◉</span><span>HOUSE MAP <small>FIELD STUDY / 04</small></span><span>NO REMOTE ASSETS</span></header>${content}</article>`;
}
const RENDERERS = {
	'index-rail': railPreview,
	'category-atlas': atlas,
	'today-ledger': todayLedger,
	'split-sheet': splitSheet,
	'card-mosaic': mosaic,
	'field-notes': fieldNotes,
	'dispatch-board': dispatchBoard,
	'focus-deck': focusDeck,
	terminal,
	'orbit-map': orbitMap
};
function appPreview(draft, state) {
	addInputPrefix = `${draft.id}-`;
	const list = byId(state.listId);
	if (draft.level <= 2) return sharedReference(draft, state.view, list);
	return RENDERERS[draft.id](draft, state.view, list);
}
function cardMarkup(draft) {
	const swatches = draft.level === 1 || draft.id === 'reference'
		? `<span class="mini-swatch swatch-bg"></span><span class="mini-swatch swatch-surface"></span><span class="mini-swatch swatch-text"></span><span class="mini-swatch swatch-accent"></span>`
		: `<span class="mini-mark ${draft.id}"></span><span class="mini-line"></span><span class="mini-dot"></span>`;
	return `<article class="draft-card draft-${draft.id}" data-card-id="${draft.id}"><div class="draft-card-art" data-draft="${draft.id}" data-mode="light"><div class="mini-identity">${esc(draft.style)}</div><div class="mini-art-inner">${swatches}<span class="mini-art-lines"><i></i><i></i><i></i></span></div></div><div class="draft-card-copy"><p class="card-kicker">${draft.level ? `LEVEL ${draft.level} · ${esc(draft.style)}` : 'REFERENCE · NOT COUNTED'}</p><h3>${esc(draft.name)}</h3><p class="draft-concept">${esc(draft.concept)}</p><p class="seam-note"><b>Seam:</b> ${esc(draft.seam)}</p><div class="draft-card-actions"><label class="compare-label"><input type="checkbox" data-action="select-draft" value="${draft.id}" ${selectedDrafts.has(draft.id) ? 'checked' : ''} ${draft.level === 0 ? 'disabled' : ''}><span>${draft.level === 0 ? 'Reference only' : 'Compare'}</span></label><button type="button" class="text-button" data-action="open-draft" data-draft-id="${draft.id}">Open preview <span aria-hidden="true">↗</span></button></div></div></article>`;
}
function galleryMarkup() {
	return `<section id="drafts" class="gallery-index" aria-labelledby="draft-index-title"><div class="section-heading"><div><p class="eyebrow">THE DIRECTION MATRIX</p><h2 id="draft-index-title">Pick a direction to inspect.</h2></div><p>20 original drafts + one current reference</p></div>${LEVELS.map((level) => `<section class="level-group" aria-labelledby="level-${level.id}"><div class="level-heading"><div><span class="level-number">${String(level.id).padStart(2, '0')}</span><h3 id="level-${level.id}">${esc(level.title)}</h3></div><p>${esc(level.sub)}</p></div><div class="draft-grid">${allDrafts.filter((draft) => draft.level === level.id).map(cardMarkup).join('')}</div></section>`).join('')}<section class="reference-group" aria-labelledby="reference-heading"><div class="level-heading"><div><span class="level-number ref-number">↗</span><h3 id="reference-heading">Current app reference</h3></div><p>Outside the twenty directions; the same representative sample and mock interactions.</p></div><div class="draft-grid reference-grid">${cardMarkup(DRAFTS[0])}</div></section></section>`;
}
function viewerMarkup(state) {
	const compare = state.compare;
	const ids = compare.length ? compare : state.draft ? [state.draft] : [];
	if (!ids.length) return '';
	const focused = ids.length === 1;
	const selected = ids.map((id) => DRAFTS.find((draft) => draft.id === id)).filter(Boolean);
	const heading = focused ? selected[0].name : `${selected.length} directions side by side`;
	return `<div class="viewer-head"><div><p class="eyebrow">${focused ? 'FOCUSED PHONE PREVIEW' : 'SIDE-BY-SIDE COMPARISON'}</p><h2>${esc(heading)}</h2><p>${focused ? esc(selected[0].concept) : 'Each card is a separate mock app. Try the same room and list interactions in every direction.'}</p></div><button class="close-viewer" type="button" data-action="close-viewer">Close preview</button></div><div class="preview-controls"><div class="view-switch" role="group" aria-label="Preview page"><button type="button" data-action="set-view" data-view="room" aria-pressed="${state.view === 'room'}">Room overview</button><button type="button" data-action="set-view" data-view="list" aria-pressed="${state.view === 'list'}">List view</button></div><label class="list-select-label">Open list <select data-action="select-list" aria-label="Choose a sample list">${LISTS.map((list) => `<option value="${list.id}" ${list.id === state.listId ? 'selected' : ''}>${esc(list.name)}</option>`).join('')}</select></label><label class="mode-select-label">Color mode <select data-action="select-mode" aria-label="Choose preview color mode"><option value="light" ${state.mode === 'light' ? 'selected' : ''}>Light</option><option value="dark" ${state.mode === 'dark' ? 'selected' : ''}>Dark</option></select></label>${focused ? '' : `<span class="compare-limit">Showing ${selected.length} of 20 drafts</span>`}</div><div class="preview-grid ${focused ? 'focused-preview' : 'comparison-preview'}">${selected.map((draft) => `<section class="preview-column" aria-label="${esc(draft.name)} prototype"><div class="preview-column-title"><span><b>${esc(draft.name)}</b><small>${draft.level ? `Level ${draft.level} · ${esc(draft.style)}` : 'Current app reference'}</small></span>${draft.level ? `<button type="button" class="remove-compare" data-action="remove-compare" data-draft-id="${draft.id}" aria-label="Remove ${esc(draft.name)} from comparison">Remove</button>` : ''}</div>${appPreview(draft, state)}<p class="preview-seam"><b>Implementation seam</b> · ${esc(draft.seam)}</p></section>`).join('')}</div><p class="viewer-note">All item and room actions are local to this page. Features not shown are illustrative only; no app behavior is inferred from the visual experiments.</p>`;
}
function syncMode() {
	const state = routeState();
	document.documentElement.dataset.mode = state.mode;
	const select = document.getElementById('mode-select');
	if (select) select.value = state.mode;
}
/** Remember the focused control, so a re-render (check, add, tag) does not drop focus to the page top. */
function captureFocus() {
	const active = document.activeElement;
	if (!active || active === document.body || !app.contains(active)) return null;
	return {
		draftId: active.closest('[data-draft-id]')?.dataset.draftId || '',
		isAddInput: Boolean(active.closest('form[data-action="add"]')),
		action: active.dataset.action || '',
		itemId: active.dataset.itemId || '',
		tag: active.dataset.tag || '',
		value: active.dataset.action === 'select-draft' ? active.value : ''
	};
}
function restoreFocus(saved) {
	if (!saved) return;
	const scope = saved.draftId ? document.querySelector(`.prototype[data-draft-id="${saved.draftId}"]`) : app;
	if (!scope) return;
	const addInput = () => scope.querySelector('form[data-action="add"] input[name="item"]');
	let target = null;
	if (saved.isAddInput) target = addInput();
	else if (saved.action) {
		target = [...scope.querySelectorAll(`[data-action="${saved.action}"]`)].find((element) =>
			(!saved.itemId || element.dataset.itemId === saved.itemId) &&
			(!saved.tag || element.dataset.tag === saved.tag) &&
			(!saved.value || element.value === saved.value)
		) ?? null;
	}
	// An item that moved to another column or left the spotlight: fall back to the preview's add field, else the preview itself.
	if (!target && saved.draftId) target = addInput() ?? Object.assign(scope, { tabIndex: -1 });
	target?.focus({ preventScroll: true });
}
function render() {
	const focus = captureFocus();
	const state = routeState();
	syncMode();
	const groups = document.getElementById('draft-groups');
	groups.innerHTML = galleryMarkup();
	const viewer = document.getElementById('viewer');
	viewer.innerHTML = viewerMarkup(state);
	viewer.hidden = !state.draft && state.compare.length === 0;
	const compareButton = document.getElementById('compare-button');
	compareButton.disabled = selectedDrafts.size < 2 || selectedDrafts.size > 4;
	compareButton.textContent = selectedDrafts.size > 4 ? 'Choose at most four' : `Compare selected${selectedDrafts.size ? ` (${selectedDrafts.size})` : ''}`;
	document.getElementById('selection-count').textContent = selectedDrafts.size > 4
		? 'Choose no more than four drafts.'
		: selectedDrafts.size > 0
			? `${selectedDrafts.size} selected. Choose ${Math.max(0, 2 - selectedDrafts.size)} more to compare, or open one focused preview.`
			: 'Choose two to four drafts to compare, or open one focused preview.';
	restoreFocus(focus);
}
function replaceAndRender(patch) { setRoute(patch, true); }

const app = document.getElementById('gallery-app');
app.addEventListener('click', (event) => {
	const button = event.target.closest('[data-action]');
	if (!button) return;
	const action = button.dataset.action;
	if (action === 'open-draft') {
		selectedDrafts.clear();
		setRoute({ draft: button.dataset.draftId, compare: [] });
		document.getElementById('viewer').scrollIntoView({ behavior: 'smooth', block: 'start' });
	} else if (action === 'room') {
		replaceAndRender({ view: 'room' });
	} else if (action === 'open-list') {
		replaceAndRender({ view: 'list', listId: button.dataset.listId });
	} else if (action === 'set-view') {
		replaceAndRender({ view: button.dataset.view });
	} else if (action === 'close-viewer') {
		setRoute({ draft: '', compare: [] });
	} else if (action === 'remove-compare') {
		const state = routeState();
		const compare = state.compare.filter((id) => id !== button.dataset.draftId);
		setRoute({ compare, draft: compare.length === 1 ? compare[0] : '' });
	} else if (action === 'edit') {
		openEditor(button.dataset.itemId);
	} else if (action === 'filter-tag') {
		const tag = button.dataset.tag;
		if (activeFilters.has(tag)) activeFilters.delete(tag); else activeFilters.add(tag);
		render();
	} else if (action === 'clear-tags') {
		activeFilters.clear();
		render();
	} else if (action === 'toggle-item-tag') {
		const list = byId(button.dataset.listId);
		const item = list.items.find((entry) => entry.id === button.dataset.itemId);
		if (item) item.tags = item.tags.includes(button.dataset.tag) ? item.tags.filter((tag) => tag !== button.dataset.tag) : [...item.tags, button.dataset.tag];
		render();
	} else if (action === 'new-list') {
		const dialog = document.getElementById('list-dialog');
		document.getElementById('new-list-name').value = '';
		dialog.showModal();
	} else if (action === 'close-dialog') {
		button.closest('dialog')?.close();
	}
});
app.addEventListener('change', (event) => {
	const target = event.target;
	if (target.matches('[data-action="select-draft"]')) {
		if (target.checked) selectedDrafts.add(target.value); else selectedDrafts.delete(target.value);
		if (selectedDrafts.size > 4) target.checked = false, selectedDrafts.delete(target.value);
		render();
	} else if (target.matches('[data-action="check"]')) {
		const list = byId(routeState().listId);
		const item = list.items.find((entry) => entry.id === target.dataset.itemId);
		if (item) item.done = target.checked;
		render();
	} else if (target.matches('[data-action="select-list"]')) {
		replaceAndRender({ listId: target.value });
	} else if (target.matches('[data-action="select-mode"]')) {
		setRoute({ mode: target.value });
	} else if (target.id === 'mode-select') {
		setRoute({ mode: target.value });
	}
});
app.addEventListener('submit', (event) => {
	const form = event.target;
	if (!form.matches('[data-action="add"]')) return;
	event.preventDefault();
	const nameInput = form.elements.namedItem('item');
	const name = nameInput.value.trim();
	if (!name) return;
	const list = byId(form.dataset.listId);
	list.items.push({ id: `new-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`, name, notes: '', quantity: 1, tags: [], due: '', done: false });
	render();
});
function openEditor(itemId) {
	const state = routeState();
	const list = byId(state.listId);
	const item = list.items.find((entry) => entry.id === itemId);
	if (!item) return;
	editing = { itemId, listId: list.id };
	document.getElementById('edit-name').value = item.name;
	document.getElementById('edit-notes').value = item.notes;
	document.getElementById('edit-quantity').textContent = item.quantity;
	document.getElementById('edit-due').value = item.due;
	document.getElementById('edit-time').value = item.due_time || '';
	document.getElementById('edit-zone').value = item.due_timezone || '';
	document.getElementById('due-fields').hidden = !item.due;
	document.getElementById('edit-tag-options').innerHTML = listTags(list).map((tag) => `<label class="tag-option"><input type="checkbox" name="tags" value="${esc(tag)}" ${item.tags.includes(tag) ? 'checked' : ''}>${esc(tag)}</label>`).join('');
	document.getElementById('edit-dialog').showModal();
}
function saveEditor(event) {
	event.preventDefault();
	const list = byId(editing?.listId);
	const item = list?.items.find((entry) => entry.id === editing?.itemId);
	const nameInput = document.getElementById('edit-name');
	const name = nameInput.value.trim();
	if (!name) {
		nameInput.setCustomValidity('Enter an item name.');
		nameInput.reportValidity();
		return;
	}
	nameInput.setCustomValidity('');
	if (item) {
		item.name = name;
		item.notes = document.getElementById('edit-notes').value.trim();
		item.quantity = Math.max(1, Math.min(999, Number(document.getElementById('edit-quantity').textContent) || 1));
		item.due = document.getElementById('edit-due').value;
		item.due_time = item.due ? document.getElementById('edit-time').value.trim() : '';
		item.due_timezone = item.due && item.due_time ? (document.getElementById('edit-zone').value.trim() || 'Europe/Oslo') : '';
		item.tags = [...document.querySelectorAll('#edit-tag-options input:checked')].map((input) => input.value);
	}
	document.getElementById('edit-dialog').close();
	render();
}
document.getElementById('edit-form').addEventListener('submit', saveEditor);
document.getElementById('list-form').addEventListener('submit', (event) => {
	event.preventDefault();
	const name = document.getElementById('new-list-name').value.trim();
	if (!name) return;
	const id = `new-list-${Date.now()}`;
	LISTS.push({ id, name, tint: 'new', items: [] });
	document.getElementById('list-dialog').close();
	replaceAndRender({ view: 'list', listId: id });
});
document.addEventListener('click', (event) => {
	const button = event.target.closest('[data-quantity-delta], [data-clear-date]');
	if (button?.hasAttribute('data-quantity-delta')) {
		const output = document.getElementById('edit-quantity');
		output.textContent = String(Math.max(1, Math.min(999, Number(output.textContent) + Number(button.dataset.quantityDelta))));
	} else if (button?.hasAttribute('data-clear-date')) {
		document.getElementById('edit-due').value = '';
		document.getElementById('edit-time').value = '';
		document.getElementById('edit-zone').value = '';
		document.getElementById('due-fields').hidden = true;
	}
});
document.getElementById('edit-due').addEventListener('change', (event) => {
	document.getElementById('due-fields').hidden = !event.target.value;
});
document.querySelectorAll('[data-close-dialog]').forEach((button) => button.addEventListener('click', () => button.closest('dialog').close()));
document.getElementById('compare-button').addEventListener('click', () => {
	if (selectedDrafts.size < 2 || selectedDrafts.size > 4) return;
	setRoute({ draft: '', compare: [...selectedDrafts] });
	document.getElementById('viewer').scrollIntoView({ behavior: 'smooth', block: 'start' });
});
document.getElementById('mode-select').addEventListener('change', (event) => setRoute({ mode: event.target.value }));
window.addEventListener('popstate', render);
render();

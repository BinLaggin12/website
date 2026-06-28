const API = '';

function getCookie(name) {
    const m = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
    return m ? decodeURIComponent(m[2]) : null;
}

function setCookie(name, value) {
    document.cookie = `${name}=${value}; path=/; max-age=86400`;
}

function deleteCookie(name) {
    document.cookie = `${name}=; path=/; max-age=0`;
}

let state = {
    userId: getCookie('user_id') || null,
    userEvents: JSON.parse(localStorage.getItem('user_events') || '[]'),
    houses: JSON.parse(localStorage.getItem('houses') || '[]'),
};

function $(sel) { return document.querySelector(sel); }
function $$(sel) { return document.querySelectorAll(sel); }

function toast(msg, type = '') {
    const t = $('#toast');
    t.textContent = msg;
    t.className = 'show ' + type;
    clearTimeout(t._hide);
    t._hide = setTimeout(() => (t.className = ''), 2500);
}

async function api(method, path, body) {
    const opts = { method, headers: {}, credentials: 'same-origin' };
    if (body) {
        opts.headers['Content-Type'] = 'application/json';
        opts.body = JSON.stringify(body);
    }
    const res = await fetch(API + path, opts);
    const data = res.headers.get('content-type')?.includes('json') ? await res.json() : null;
    return { status: res.status, data };
}

//User contruls

async function createUser() {
    const { data } = await api('POST', '/user/create');
    state.userId = data.user_id;
    setCookie('user_id', data.user_id);
    toast('User created!', 'success');
    renderUser();
}

function clearUser() {
    state.userId = null;
    deleteCookie('user_id');
    toast('User cleared');
    renderUser();
    renderUserHeatmap();
    renderRentals();
}

function renderUser() {
    const info = $('#user-info');
    const clearBtn = $('#btn-clear-user');
    if (state.userId) {
        info.innerHTML = `<p><strong>ID:</strong> <code>${state.userId}</code></p>`;
        clearBtn.style.display = 'inline-block';
    } else {
        info.innerHTML = '<p class="muted">No user created yet.</p>';
        clearBtn.style.display = 'none';
    }
}

//Houses

async function createHouse() {
    const { data } = await api('POST', '/house/create');
    const list = $('#houses-list');
    const el = document.createElement('span');
    el.className = 'house-item';
    el.textContent = data.house_id;
    list.appendChild(el);
    toast('House created!', 'success');
}

async function rentHouse() {
    const houseId = $('#input-rent-house-id').value.trim();
    if (!houseId) return toast('Enter a house ID', 'error');
    if (!state.userId) return toast('Create a user first', 'error');
    const { status, data } = await api('POST', `/house/${houseId}/rent`, { tenant: 'User' });
    if (status === 200) {
        $('#rent-result').innerHTML = `<span class="success" style="padding:0.3rem 0.6rem;border-radius:4px">Rented! ID: <code>${data.rental_id}</code></span>`;
        toast('House rented!', 'success');
        renderRentals();
    } else if (status === 409) {
        $('#rent-result').innerHTML = `<span style="color:#e74c3c">House is already rented</span>`;
        toast('House already rented', 'error');
    } else {
        $('#rent-result').innerHTML = `<span style="color:#e74c3c">Error: ${data?.detail || status}</span>`;
    }
}

async function checkLock() {
    const houseId = $('#input-lock-house-id').value.trim();
    if (!houseId) return toast('Enter a house ID', 'error');
    const { status, data } = await api('GET', `/house/${houseId}/current_lock`);
    if (status === 200) {
        $('#lock-result').innerHTML = `<span style="color:#155724">Locked by: <code>${data.user_id}</code></span>`;
    } else {
        $('#lock-result').innerHTML = `<span class="muted">No active lock</span>`;
    }
}

//Rentals

async function renderRentals() {
    const container = $('#rentals-list');
    if (!state.userId) {
        container.innerHTML = '<p class="muted">Create a user to see rentals.</p>';
        return;
    }
    const { status, data } = await api('GET', '/user/rentals');
    if (status !== 200 || !data || data.length === 0) {
        container.innerHTML = '<p class="muted">No rentals found.</p>';
        return;
    }
    container.innerHTML = data.map(r => `
        <div class="rental-item">
            <div class="info">
                <div><span class="status ${r.status}">${r.status}</span></div>
                <div class="rental-id">${r.rental_id}</div>
                <div style="font-size:0.8rem;color:#888">House: <code>${r.house_id}</code></div>
            </div>
            <div class="actions">
                <button class="btn secondary" onclick="viewRental('${r.rental_id}')">View</button>
                ${r.status === 'active' ? `<button class="btn danger" onclick="cancelRental('${r.rental_id}')">Cancel</button>` : ''}
            </div>
        </div>
    `).join('');
}

async function viewRental(rentalId) {
    const { status, data } = await api('GET', `/rental/${rentalId}`);
    if (status !== 200) return toast('Forbidden or not found', 'error');
    $('#rentals-section').style.display = 'none';
    $('#rental-detail-section').style.display = 'block';

    // show editable JSON payload and actions
    const container = document.createElement('div');
    container.style.display = 'flex';
    container.style.flexDirection = 'column';
    container.style.gap = '0.5rem';

    const info = document.createElement('div');
    info.innerHTML = `<div style="font-size:0.9rem;color:#333">
        <div><strong>Rental:</strong> <code>${rentalId}</code></div>
        <div><strong>Status:</strong> <span style="text-transform:capitalize">${data.status}</span></div>
        <div><strong>House:</strong> <code>${data.house_id}</code></div>
        <div><strong>Created:</strong> <span>${new Date(data.created_at).toLocaleString()}</span></div>
    </div>`;

    // Only allow editing the `data` object of the rental
    const ta = document.createElement('textarea');
    ta.style.minHeight = '200px';
    ta.style.width = '100%';
    ta.style.fontFamily = 'monospace';
    ta.style.fontSize = '0.85rem';
    ta.title = 'Edit only the rental.data JSON object';
    ta.value = JSON.stringify(data.data ?? {}, null, 2);

    const actions = document.createElement('div');
    actions.style.display = 'flex';
    actions.style.gap = '0.5rem';

    const btnSave = document.createElement('button');
    btnSave.className = 'btn primary';
    btnSave.textContent = 'Save';
    btnSave.onclick = async () => {
        await updateRental(rentalId, ta);
    };

    const btnBack = document.createElement('button');
    btnBack.className = 'btn secondary';
    btnBack.textContent = 'Back to list';
    btnBack.onclick = () => {
        $('#rental-detail-section').style.display = 'none';
        $('#rentals-section').style.display = 'block';
    };

    actions.appendChild(btnSave);
    actions.appendChild(btnBack);

    container.appendChild(info);
    container.appendChild(ta);
    container.appendChild(actions);

    const det = $('#rental-detail');
    det.innerHTML = '';
    det.appendChild(container);
}

async function updateRental(rentalId, textarea) {
    let payload;
    try {
        payload = JSON.parse(textarea.value);
    } catch (e) {
        toast('Invalid JSON payload', 'error');
        return;
    }

    const { status, data } = await api('POST', `/rental/${rentalId}/update`, payload);
    if (status === 200) {
        toast('Rental updated', 'success');
        // refresh rental detail with server state
        const refreshed = await api('GET', `/rental/${rentalId}`);
        if (refreshed.status === 200 && refreshed.data) textarea.value = JSON.stringify(refreshed.data.data ?? {}, null, 2);
        renderRentals();
    } else if (status === 403) {
        toast(data?.detail || 'Forbidden', 'error');
    } else if (status === 404) {
        toast(data?.detail || 'Not found', 'error');
    } else {
        toast(data?.detail || `Error ${status}`, 'error');
    }
}

async function cancelRental(rentalId) {
    if (!confirm('Cancel this rental?')) return;
    const { status } = await api('POST', `/rental/${rentalId}/cancel`);
    if (status === 200) {
        toast('Rental cancelled', 'success');
        renderRentals();
    } else {
        toast('Failed to cancel', 'error');
    }
}

//grid maps like github

const HM_COLS = 10;

function saveUserEvents() {
    localStorage.setItem('user_events', JSON.stringify(state.userEvents));
}

function saveHouses() {
    localStorage.setItem('houses', JSON.stringify(state.houses));
}

function renderUserHeatmap() {
    const el = $('#user-heatmap');
    const count = $('#user-hm-count');
    const events = state.userEvents;
    count.textContent = events.length;

    const grid = document.createElement('div');
    grid.className = 'heatmap';
    for (const [idx, e] of events.entries()) {
        const cell = document.createElement('span');
        cell.className = 'hm-cell hm-cell-user';
        if (e.id === state.userId) cell.classList.add('hm-cell-active');
        cell.title = `${e.id}\n${new Date(e.ts).toLocaleString()}`;
        cell.onclick = () => selectUser(e.id);
        cell.ondblclick = () => removeUserEvent(idx);
        grid.appendChild(cell);
    }
    el.innerHTML = '';
    el.appendChild(grid);
}

function selectUser(id) {
    state.userId = id;
    setCookie('user_id', id);
    toast('Switched to user', 'success');
    renderUser();
    renderUserHeatmap();
    renderRentals();
}

function removeUserEvent(idx) {
    const e = state.userEvents[idx];
    if (!confirm(`Remove user ${e.id.slice(0, 8)}… from activity?`)) return;
    state.userEvents.splice(idx, 1);
    saveUserEvents();
    if (state.userId === e.id) {
        // if active user was removed, pick another or clear
        const next = state.userEvents.length ? state.userEvents[0].id : null;
        state.userId = next;
        if (next) setCookie('user_id', next);
        else clearUser();
    }
    renderUserHeatmap();
    renderUser();
    renderRentals();
}

async function renderHouseHeatmap() {
    const el = $('#house-heatmap');
    const totalEl = $('#house-hm-total');
    const occEl = $('#house-hm-occ');
    const houses = state.houses;

    totalEl.textContent = houses.length;

    if (houses.length === 0) {
        el.innerHTML = '<p class="muted" style="font-size:0.8rem">No houses created yet.</p>';
        occEl.textContent = '0';
        return;
    }

    const grid = document.createElement('div');
    grid.className = 'heatmap';
    let occupied = 0;

    for (const h of houses) {
        const cell = document.createElement('span');
        cell.className = 'hm-cell';
        cell.title = h.id;

        if (h.status === 'occupied') {
            cell.classList.add('hm-cell-occ');
            occupied++;
        } else {
            cell.classList.add('hm-cell-free');
        }

        cell.onclick = () => {
            $('#input-rent-house-id').value = h.id;
            $('#input-rent-house-id').focus();
        };
        grid.appendChild(cell);
    }

    occEl.textContent = occupied;
    el.innerHTML = '';
    el.appendChild(grid);
}

async function refreshHouseStatuses() {
    const houses = state.houses;
    if (houses.length === 0) return;

    // get active rentals for current user
    let activeRentalHouses = new Set();
    if (state.userId) {
        const { status, data } = await api('GET', '/user/rentals');
        if (status === 200 && data) {
            for (const r of data) {
                if (r.status === 'active') activeRentalHouses.add(r.house_id);
            }
        }
    }

    for (const h of houses) {
        if (activeRentalHouses.has(h.id)) {
            h.status = 'occupied';
        } else {
            // check lock from anyone
            const { status } = await api('GET', `/house/${h.id}/current_lock`);
            h.status = status === 200 ? 'occupied' : 'free';
        }
    }
    saveHouses();
    renderHouseHeatmap();
}

// Override handlers to track events
const _origCreateUser = createUser;
createUser = async function () {
    await _origCreateUser();
    state.userEvents.push({ ts: Date.now(), id: state.userId });
    saveUserEvents();
    renderUserHeatmap();
};

const _origCreateHouse = createHouse;
createHouse = async function () {
    await _origCreateHouse();
    // re-parse the last house-id from the DOM
    const items = document.querySelectorAll('#houses-list .house-item');
    if (items.length) {
        const hid = items[items.length - 1].textContent;
        state.houses.push({ id: hid, status: 'free' });
        saveHouses();
        renderHouseHeatmap();
    }
};

const _origRentHouse = rentHouse;
rentHouse = async function () {
    const houseId = $('#input-rent-house-id').value.trim();
    await _origRentHouse();
    const h = state.houses.find(x => x.id === houseId);
    if (h) {
        const { status } = await api('GET', `/house/${houseId}/current_lock`);
        h.status = status === 200 ? 'occupied' : 'free';
        saveHouses();
        renderHouseHeatmap();
    }
};

const _origCancelRental = cancelRental;
cancelRental = async function (rentalId) {
    await _origCancelRental(rentalId);
    // refresh all houses
    await refreshHouseStatuses();
};

//Init

renderUser();

$('#btn-create-user').onclick = createUser;
$('#btn-clear-user').onclick = clearUser;
$('#btn-create-house').onclick = createHouse;
$('#btn-rent-house').onclick = rentHouse;
$('#btn-check-lock').onclick = checkLock;
$('#btn-refresh-rentals').onclick = renderRentals;

$('#input-rent-house-id').addEventListener('keydown', e => { if (e.key === 'Enter') rentHouse(); });
$('#input-lock-house-id').addEventListener('keydown', e => { if (e.key === 'Enter') checkLock(); });

// init heatmaps
renderUserHeatmap();
renderHouseHeatmap();
if (state.houses.length > 0) refreshHouseStatuses();

if (state.userId) renderRentals();

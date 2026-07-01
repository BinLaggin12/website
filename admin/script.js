var TOKEN = localStorage.getItem('admin_token');
var USERNAME = localStorage.getItem('admin_username');

function isLoggedIn() {
    return TOKEN && TOKEN.length > 0;
}

function requireAuth() {
    if (!isLoggedIn()) {
        window.location.href = '/admin/login.html';
    }
}

function api(path, method, body) {
    var opts = {
        method: method || 'GET',
        headers: { 'Content-Type': 'application/json' },
        cache: 'no-cache',
    };
    if (TOKEN) {
        opts.headers['Authorization'] = 'Bearer ' + TOKEN;
    }
    if (body) {
        opts.body = JSON.stringify(body);
    }
    return fetch('/api/admin' + path, opts).then(function(r) {
        if (r.status === 401) {
            localStorage.removeItem('admin_token');
            localStorage.removeItem('admin_username');
            window.location.href = '/admin/login.html';
            throw new Error('Unauthorized');
        }
        return r.json().then(function(data) {
            if (!r.ok) throw new Error(data.detail || 'Request failed');
            return data;
        });
    });
}

function showMessage(msg, type) {
    var el = document.getElementById('message');
    if (!el) return;
    el.textContent = msg;
    el.className = 'message ' + (type || 'success');
    el.style.display = 'block';
    setTimeout(function() { el.style.display = 'none'; }, 4000);
}

function escapeHtml(text) {
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(text));
    return div.innerHTML;
}

function toggleBookingsMenu(event) {
    event.stopPropagation();
    var menu = document.getElementById('bookingsMenu');
    menu.classList.toggle('show');
}

document.addEventListener('click', function() {
    var menu = document.getElementById('bookingsMenu');
    if (menu) menu.classList.remove('show');
});

function getUrlParam(name) {
    var params = new URLSearchParams(window.location.search);
    return params.get(name);
}

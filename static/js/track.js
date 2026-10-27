(function () {
    var script = document.currentScript;
    if (!script) {
        return;
    }
    var site = script.getAttribute('data-site');
    if (!site) {
        return;
    }
    var endpoint = new URL('/api/collect', script.src).href;
    var storageKey = 'hubtrack_sid';
    var lastPath = '';

    function sessionId() {
        try {
            var existing = sessionStorage.getItem(storageKey);
            if (existing) {
                return existing;
            }
            var created = (window.crypto && crypto.randomUUID)
                ? crypto.randomUUID()
                : 's' + Math.random().toString(36).slice(2) + Date.now().toString(36);
            sessionStorage.setItem(storageKey, created);
            return created;
        } catch (err) {
            return '';
        }
    }

    function send(path) {
        var sid = sessionId();
        if (!sid) {
            return;
        }
        var body = JSON.stringify({
            site: site,
            path: path || (location.pathname || '/'),
            referrer: document.referrer || '',
            session: sid
        });
        if (navigator.sendBeacon) {
            navigator.sendBeacon(endpoint, body);
            return;
        }
        fetch(endpoint, {
            method: 'POST',
            body: body,
            keepalive: true,
            mode: 'cors',
            credentials: 'omit'
        });
    }

    function track(force) {
        var path = location.pathname || '/';
        if (!force && path === lastPath) {
            return;
        }
        lastPath = path;
        send(path);
    }

    window.hubtrack = window.hubtrack || {};
    window.hubtrack.pageview = function (path) {
        var next = path || location.pathname || '/';
        lastPath = next;
        send(next);
    };

    var pushState = history.pushState;
    history.pushState = function () {
        var result = pushState.apply(this, arguments);
        lastPath = '';
        track(false);
        return result;
    };
    var replaceState = history.replaceState;
    history.replaceState = function () {
        var result = replaceState.apply(this, arguments);
        track(false);
        return result;
    };
    window.addEventListener('popstate', function () {
        lastPath = '';
        track(false);
    });

    if (document.readyState === 'complete') {
        track(false);
    } else {
        window.addEventListener('load', function () {
            track(false);
        });
    }
})();

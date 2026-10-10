/* Count real detail-page opens, not the multiple requests used by the photo gallery. */
(function () {
  const id = new URLSearchParams(location.search).get('id');
  if (!id || !window.fetch) return;
  let visitorId = '';
  try {
    visitorId = localStorage.getItem('bigpaw_view_visitor_v1') || '';
    if (!/^[a-zA-Z0-9_-]{12,96}$/.test(visitorId)) {
      visitorId = (window.crypto && window.crypto.randomUUID)
        ? window.crypto.randomUUID().replace(/-/g, '')
        : 'visitor_' + Date.now().toString(36) + Math.random().toString(36).slice(2);
      localStorage.setItem('bigpaw_view_visitor_v1', visitorId);
    }
  } catch (_e) {
    visitorId = 'visitor_' + Date.now().toString(36) + Math.random().toString(36).slice(2);
  }
  fetch('/api/puppies/' + encodeURIComponent(id) + '/view', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ visitorId: visitorId }),
    keepalive: true
  }).catch(function () { /* Analytics must never block puppy details. */ });
})();

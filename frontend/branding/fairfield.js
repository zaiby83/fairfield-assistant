/*
 * City of Fairfield layout additions for LibreChat v0.8.8 (styles in
 * fairfield-theme.css). Loaded by a <script defer> that the api `command` in
 * docker-compose.override.yml adds to index.html.
 *
 * Adds, without touching LibreChat's own nodes beyond a class name:
 *  - header band: seal + "City of Fairfield" wordmark, "AI Assistant · Staff only" label
 *  - new-chat screen: "How can we help?" section label and three quick-start tiles
 *    that put a starter prompt in the message box (never sends it).
 *
 * React re-renders can drop these, so a MutationObserver re-applies them.
 * Everything is idempotent and fails quietly if LibreChat's markup changes.
 */
(function () {
  'use strict';

  var SEAL = 'assets/icon-192x192.png'; // relative to <base href>

  var TILES = [
    {
      cls: 'ff-tile--cream',
      title: 'Draft',
      sub: 'Memos, emails, notices',
      prompt:
        'Draft a short, professional email to [recipient] about [topic]. ' +
        'Keep it clear and courteous, and end with the next step I need from them.',
    },
    {
      cls: 'ff-tile--moss',
      title: 'Summarize',
      sub: 'Reports and agendas',
      prompt:
        'Summarize the text below in plain language. List the key decisions, ' +
        'dates, costs and action items as bullet points.\n\n[paste the text here]',
    },
    {
      cls: 'ff-tile--blue',
      title: 'Explain',
      sub: 'Plain-language rewrites',
      prompt:
        'Rewrite the text below for Fairfield residents in plain language ' +
        '(about an 8th-grade reading level). Keep every fact the same.\n\n[paste the text here]',
    },
  ];

  var CHEVRON =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<path d="M6 7l6 6 6-6"/><path d="M6 13l6 6 6-6"/></svg>';

  function el(tag, cls, html) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (html != null) node.innerHTML = html;
    return node;
  }

  /* Put text in the composer the way typing would, so React sees it. */
  function fillComposer(text) {
    var ta = document.querySelector('[data-testid="composer-surface"] textarea') ||
      document.querySelector('textarea');
    if (!ta) return;
    var setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set;
    setter.call(ta, text);
    ta.dispatchEvent(new Event('input', { bubbles: true }));
    ta.focus();
    var start = text.indexOf('[');
    if (start >= 0) ta.setSelectionRange(start, text.indexOf(']', start) + 1);
  }

  function decorateBar() {
    var picker = document.querySelector('[data-testid="model-selector-button"]');
    var bar = picker && picker.closest('.absolute.top-0');
    if (!bar) return;
    bar.classList.add('ff-bar');
    if (bar.nextElementSibling) bar.nextElementSibling.classList.add('ff-under-bar');

    if (!bar.querySelector('.ff-wordmark')) {
      var mark = el(
        'div',
        'ff-wordmark',
        '<img alt="" src="' + SEAL + '"><div><small>City of</small><strong>Fairfield</strong></div>'
      );
      mark.setAttribute('role', 'img');
      mark.setAttribute('aria-label', 'City of Fairfield');
      var grow = bar.querySelector(':scope > .flex-1');
      bar.insertBefore(mark, grow || bar.firstChild);
    }
    if (!bar.querySelector('.ff-bar-label')) {
      var grow2 = bar.querySelector(':scope > .flex-1');
      var label = el('div', 'ff-bar-label', 'AI Assistant &middot; Staff only');
      if (grow2) grow2.after(label);
    }
  }

  function decorateLanding() {
    var heading = document.querySelector('p.split-parent');
    var row = heading && heading.parentElement;
    var box = row && row.parentElement;
    if (!box) {
      // Left the new-chat screen: drop tiles that outlived it.
      document.querySelectorAll('.ff-tiles').forEach(function (n) { n.remove(); });
      return;
    }

    if (!box.querySelector('.ff-kicker')) {
      box.insertBefore(el('div', 'ff-kicker', 'How can we help?'), row);
    }
    // Tiles go under the message box: the landing block above it has
    // max-height 0 on desktop, so anything taller overflows onto the composer.
    var area = heading.closest('.scrollbar-gutter-spacer');
    if (area && !area.querySelector(':scope > .ff-tiles')) {
      var grid = el('div', 'ff-tiles');
      grid.setAttribute('role', 'group');
      grid.setAttribute('aria-label', 'Quick start');
      TILES.forEach(function (t) {
        var btn = el('button', 'ff-tile ' + t.cls, '<b>' + t.title + '</b><span>' + t.sub + '</span>' + CHEVRON);
        btn.type = 'button';
        btn.setAttribute('aria-label', t.title + ': ' + t.sub + '. Puts a starter prompt in the message box.');
        btn.addEventListener('click', function () {
          fillComposer(t.prompt);
        });
        grid.appendChild(btn);
      });
      area.appendChild(grid);
    }
  }

  var queued = false;
  function apply() {
    queued = false;
    try {
      decorateBar();
      decorateLanding();
    } catch (e) {
      /* LibreChat markup changed; leave the stock UI alone. */
    }
  }
  function schedule() {
    if (!queued) {
      queued = true;
      requestAnimationFrame(apply);
    }
  }

  function start() {
    new MutationObserver(schedule).observe(document.body, { childList: true, subtree: true });
    schedule();
  }
  if (document.body) start();
  else document.addEventListener('DOMContentLoaded', start);
})();

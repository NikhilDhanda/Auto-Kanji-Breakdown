(function (root) {
    'use strict';
    var positions = {left:'left', right:'right', top:'top', bottom:'bottom', middle:'middle',
        nyo:'lower-left', nyoc:'inside', tare:'upper-left', tarec:'inside',
        kamae:'enclosure', kamaec:'inside', '\u2ff5A':'upper enclosure',
        '\u2ff5B':'inside', '\u2ff61':'inside', '\u2ff62':'lower enclosure'};
    function strings(value) {
        return Array.isArray(value) ? value.filter(function (x) { return typeof x === 'string' && x.trim(); }) : [];
    }
    function glosses(values) {
        var plain = [], fallback = [];
        strings(values).forEach(function (value) {
            value = value.trim();
            if (/radical(?: variant)?\s*\(no\.\s*\d+\)/i.test(value)) {
                var clean = value.replace(/\s+radical(?: variant)?\s*\(no\.\s*\d+\)\s*$/i, '').trim();
                if (clean !== value && clean && !/^(?:left|right|top|bottom)\s+village$/i.test(clean)) {
                    clean.split(/\s+or\s+/i).forEach(function (part) { fallback.push(part); });
                }
            } else if (!/\d|\bcounter for\b|\b(?:ordinal|numeral|trigram)\b/i.test(value)) { plain.push(value); }
        });
        // Plain component senses get one source-first anchor. A radical-only
        // fallback can retain two short alternatives (e.g. long stride/stretching).
        var chosen = plain.length ? plain : fallback;
        return chosen.filter(function (v, i) { return chosen.indexOf(v) === i; }).slice(0, plain.length ? 1 : 2);
    }
    function compact(values, maxCount, maxLength, separator) {
        values = strings(values);
        var visible = [];
        values.some(function (value) {
            if (visible.length && (visible.length >= maxCount ||
                    Array.from(visible.concat([value]).join(separator)).length > maxLength)) { return true; }
            visible.push(value); return false;
        });
        return {visible:visible, hidden:values.length - visible.length};
    }
    function position(node) {
        if (Object.prototype.hasOwnProperty.call(positions, node.position)) { return positions[node.position]; }
        var via = Array.isArray(node.via) ? node.via : [];
        var useful = via.filter(function (v) { return v && Object.prototype.hasOwnProperty.call(positions, v.position); });
        // Multiple hidden roles (even identical ones) are ambiguous.
        return useful.length === 1 && via.length === 1 ? positions[useful[0].position] : '';
    }
    function parse(text) {
        try {
            var data = JSON.parse(text);
            if (!data || data.version !== 1 || !Array.isArray(data.entries)) { return null; }
            var count = 0;
            function valid(node, depth) {
                count++;
                return count <= 10000 && depth < 40 && node && typeof node.char === 'string' &&
                    Array.from(node.char).length === 1 && !Object.prototype.hasOwnProperty.call(node, 'part') &&
                    (!Object.prototype.hasOwnProperty.call(node, 'children') ||
                     (Array.isArray(node.children) && node.children.every(function (n) { return valid(n, depth + 1); })));
            }
            return data.entries.every(function (n) { return valid(n, 0); }) ? data : null;
        } catch (_) { return null; }
    }
    function element(doc, tag, cls, text) {
        var el = doc.createElement(tag);
        if (cls) { el.className = cls; }
        if (text !== undefined) { el.textContent = text; }
        return el;
    }
    function badge(doc, parent, cls, text) { parent.appendChild(element(doc, 'span', cls, text)); }
    function radical(doc, parent, node) {
        if (node.radical !== 'general') { return; }
        parent.classList.add('akb-radical');
        var mark = element(doc, 'span', 'akb-radical-mark', '★');
        mark.title = 'Radical'; mark.setAttribute('aria-label', 'Radical'); parent.appendChild(mark);
    }
    function toggle(doc, target, label, expanded) {
        var button = element(doc, 'button', 'akb-toggle');
        var chevron = element(doc, 'span', 'akb-chevron');
        chevron.setAttribute('aria-hidden', 'true'); button.appendChild(chevron);
        button.type = 'button'; button.title = label;
        button.setAttribute('aria-label', label); button.setAttribute('aria-expanded', String(expanded));
        target.hidden = !expanded;
        button.addEventListener('click', function (event) {
            event.stopPropagation();
            var open = button.getAttribute('aria-expanded') !== 'true';
            button.setAttribute('aria-expanded', String(open)); target.hidden = !open;
        });
        return button;
    }
    function limitedText(doc, parent, values, cls, prefix, separator, label, maxCount, maxLength) {
        values = strings(values);
        if (!values.length) { return; }
        var limit = compact(values, maxCount, maxLength, separator);
        var container = element(doc, 'span', cls), text = element(doc, 'span', 'akb-list-text');
        text.textContent = prefix + limit.visible.join(separator); container.appendChild(text);
        if (limit.hidden) {
            var button = element(doc, 'button', 'akb-more', '+' + limit.hidden);
            button.type = 'button'; button.setAttribute('aria-expanded', 'false');
            button.setAttribute('aria-label', 'Show all ' + label); button.title = 'Show all ' + label;
            button.addEventListener('click', function (event) {
                event.stopPropagation();
                var open = button.getAttribute('aria-expanded') !== 'true';
                button.setAttribute('aria-expanded', String(open));
                text.textContent = prefix + (open ? values : limit.visible).join(separator);
                button.textContent = open ? 'Less' : '+' + limit.hidden;
                button.title = (open ? 'Show fewer ' : 'Show all ') + label;
                button.setAttribute('aria-label', button.title);
            });
            container.appendChild(button);
        }
        parent.appendChild(container);
    }
    function branch(doc, nodes) {
        var list = element(doc, 'ul', 'akb-tree');
        nodes.forEach(function (node) {
            var li = element(doc, 'li', 'akb-node'), row = element(doc, 'div', 'akb-component-row');
            row.appendChild(element(doc, 'span', 'akb-component-char', node.char)); radical(doc, row, node);
            var label = position(node); if (label) { badge(doc, row, 'akb-position', label); }
            li.appendChild(row);
            var meanings = glosses(node.meanings);
            if (meanings.length) { li.appendChild(element(doc, 'div', 'akb-component-meaning', meanings.join('; '))); }
            if (node.children && node.children.length) {
                var nested = branch(doc, node.children);
                row.appendChild(toggle(doc, nested, 'Components of ' + node.char, false)); li.appendChild(nested);
            }
            list.appendChild(li);
        });
        return list;
    }
    function sources(doc, host, data) {
        var footer = element(doc, 'div', 'akb-sources');
        var panel = element(doc, 'div', 'akb-sources-panel');
        var button = element(doc, 'button', 'akb-sources-toggle', 'ⓘ');
        button.type = 'button'; button.title = 'Sources & licences';
        button.setAttribute('aria-label', 'Sources and licences');
        button.setAttribute('aria-expanded', 'false'); panel.hidden = true;
        button.addEventListener('click', function (event) {
            event.stopPropagation(); panel.hidden = !panel.hidden;
            button.setAttribute('aria-expanded', String(!panel.hidden));
        });
        function line(text) { panel.appendChild(element(doc, 'div', '', text)); }
        function heading(text) { panel.appendChild(element(doc, 'strong', 'akb-source-heading', text)); }
        function link(label, url) {
            var a = element(doc, 'a', '', label); a.href = url;
            a.addEventListener('click', function (event) { event.stopPropagation(); });
            panel.appendChild(a); panel.appendChild(doc.createTextNode(' '));
        }
        heading('Kanji data');
        line('KANJIDIC2');
        line('James William Breen and the Electronic Dictionary Research and Development Group (EDRDG)');
        line('Creative Commons Attribution-ShareAlike 4.0');
        link('Official source', 'https://www.edrdg.org/wiki/KANJIDIC_Project.html');
        link('EDRDG terms', 'https://www.edrdg.org/edrdg/licence.html');
        link('CC BY-SA 4.0', 'https://creativecommons.org/licenses/by-sa/4.0/');
        heading('Structure data');
        line('KanjiVG');
        line('Ulrich Apel and contributors');
        line('Creative Commons Attribution-ShareAlike 3.0');
        link('Official source', 'https://kanjivg.tagaini.net/');
        link('CC BY-SA 3.0', 'https://creativecommons.org/licenses/by-sa/3.0/');
        heading('Auto Kanji Breakdown');
        line('Database compilation and transformation by Nik Dhanda.');
        link('Project on GitHub', 'https://github.com/NikhilDhanda/Auto-Kanji-Breakdown');
        line('Software licence: AGPL-3.0-or-later');
        line('Combined adapted database: CC BY-SA 4.0.');
        line('No endorsement by the source projects is implied.');
        heading('This breakdown');
        var p = data.provenance;
        if (p && typeof p.kd === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(p.kd) &&
                typeof p.vg === 'string' && /^r?\d{8}$/.test(p.vg)) {
            line('KANJIDIC2 snapshot: ' + p.kd);
            line('KanjiVG: ' + p.vg);
        } else { line('Data snapshot details unavailable for this previously generated breakdown.'); }
        footer.appendChild(button); footer.appendChild(panel); host.appendChild(footer);
    }
    function render(host, data) {
        var doc = host.ownerDocument;
        host.textContent = '';
        if (!data || !data.entries.length) { return; }
        data.entries.forEach(function (node) {
            var card = element(doc, 'section', 'akb-card');
            var heading = element(doc, 'div', 'akb-heading');
            heading.appendChild(element(doc, 'span', 'akb-main-char', node.char)); radical(doc, heading, node);
            var readings = node.readings || {};
            [['on','音: ','akb-on'], ['kun','訓: ','akb-kun']].forEach(function (spec) {
                var values = strings(readings[spec[0]]);
                limitedText(doc, heading, values, 'akb-reading ' + spec[2], spec[1], ' · ',
                    (spec[0] === 'on' ? 'onyomi' : 'kunyomi') + ' for ' + node.char, 4, 26);
            });
            card.appendChild(heading);
            var meanings = strings(node.meanings);
            limitedText(doc, card, meanings, 'akb-main-meaning', '', '; ', 'meanings for ' + node.char, 4, 90);
            var meta = element(doc, 'div', 'akb-meta');
            [['strokes','Strokes: '], ['frequency','Freq #']].forEach(function (spec) {
                var n = node[spec[0]];
                if (typeof n === 'number' && isFinite(n) && n > 0) {
                    var chip = element(doc, 'span', 'akb-meta-chip', spec[1] + n);
                    if (spec[0] === 'frequency') {
                        chip.title = 'Frequency rank'; chip.setAttribute('aria-label', 'Frequency rank ' + n);
                    }
                    meta.appendChild(chip);
                }
            });
            if (meta.childNodes.length) { card.appendChild(meta); }
            if (node.children && node.children.length) {
                var children = branch(doc, node.children);
                var main = toggle(doc, children, 'Breakdown of ' + node.char, false);
                main.classList.add('akb-main-toggle');
                card.classList.add('akb-expandable');
                heading.appendChild(main); card.appendChild(children);
                // The section is not a button: nested buttons retain their own
                // semantics. Its native main button handles keyboard activation.
                card.addEventListener('click', function (event) {
                    if (event.defaultPrevented || event.target.closest('button,a,input,select,textarea,[contenteditable]')) { return; }
                    var selection = doc.defaultView.getSelection();
                    if (selection && !selection.isCollapsed) { return; }
                    main.click();
                });
            }
            host.appendChild(card);
        });
        sources(doc, host, data);
    }
    function mountAll(doc) {
        var roots = Array.prototype.slice.call(doc.querySelectorAll('.akb-root[data-akb-owner]'));
        roots.forEach(function (host, index) {
            // FrontSide can include a front block. Keep the last explicit block.
            if (roots.slice(index + 1).some(function (other) { return other.getAttribute('data-akb-owner') === host.getAttribute('data-akb-owner'); })) {
                host.parentNode.removeChild(host); return;
            }
            if (host.getAttribute('data-akb-ready')) { return; }
            var source = host.querySelector('.akb-data');
            var data = parse(source ? source.textContent : '');
            host.setAttribute('data-akb-ready', '1'); render(host, data);
        });
    }
    var api = {version:6, glosses:glosses, compact:compact, position:position, parse:parse, render:render, mountAll:mountAll};
    if (typeof module !== 'undefined' && module.exports) { module.exports = api; }
    else { root.AutoKanjiBreakdown = api; mountAll(root.document); }
}(typeof window !== 'undefined' ? window : this));

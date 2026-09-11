/* No dependencies: node tests/test_renderer.js */
'use strict';
const assert = require('node:assert/strict');
const renderer = require('../src/akb/web/renderer.js');
let tests = 0;
function test(name, body) { body(); tests++; console.log('ok - ' + name); }
test('valid, empty, malformed, unsupported and optional payloads', () => {
    assert.equal(renderer.parse(''), null);
    assert.equal(renderer.parse('{'), null);
    assert.equal(renderer.parse('{"version":2,"entries":[]}'), null);
    assert.deepEqual(renderer.parse('{"version":1,"entries":[]}').entries, []);
    assert.equal(renderer.parse('{"version":1,"entries":[{"char":"𠮟"}]}').entries[0].char, '𠮟');
    assert.equal(renderer.parse('{"version":1,"entries":[{"char":""}]}'), null);
    assert.equal(renderer.parse('{"version":1,"entries":[{"char":"二","part":"1"}]}'), null);
    assert.equal(renderer.parse('{"version":1,"entries":[{"char":"人","children":null}]}'), null);
});
test('deterministic concise glosses and radical boilerplate', () => {
    assert.deepEqual(renderer.glosses(['brush','finally','self','relate','follow','here','fast','writing brush radical (no. 129)']), ['brush']);
    assert.deepEqual(renderer.glosses(['hill','mound','left village radical (no. 170)']), ['hill']);
    assert.deepEqual(renderer.glosses(['long stride or stretching radical (no. 54)']), ['long stride','stretching']);
    assert.deepEqual(renderer.glosses(['radical (no. 1)']), []);
    assert.deepEqual(renderer.glosses(['one','one','two','three']), ['one']);
    assert.deepEqual(renderer.glosses(['capital','10**16']), ['capital']);
    assert.deepEqual(renderer.glosses(['10**16','capital']), ['capital']);
    assert.deepEqual(renderer.glosses(['counter for buildings','tree','wood']), ['tree']);
    ['woman','tree','good','foot','mouth','hemp','stone'].forEach(x => assert.deepEqual(renderer.glosses([x,'other']), [x]));
});
test('reading/meaning compaction is deterministic and preserves complete source arrays', () => {
    const values = ['い.きる','い.かす','い.ける','う.まれる','うま.れる','お.う'];
    const before = JSON.stringify(values);
    assert.equal(renderer.compact(values,4,26,' · ').hidden, 2);
    assert.equal(JSON.stringify(values), before);
    assert.deepEqual(renderer.compact(['ジン','ニン'],4,26,' · '), {visible:['ジン','ニン'],hidden:0});
    assert.deepEqual(renderer.compact(['a'.repeat(100),'next'],4,26,' · '), {visible:['a'.repeat(100)],hidden:1});
    assert.equal(renderer.compact(['one','two','three','four','five'],4,90,'; ').hidden,1);
    assert.deepEqual(renderer.compact([],4,90,'; '),{visible:[],hidden:0});
});
test('all positions and conservative via contexts', () => {
    const positions = {left:'left',right:'right',top:'top',bottom:'bottom',middle:'middle',nyo:'lower-left',nyoc:'inside',
        tare:'upper-left',tarec:'inside',kamae:'enclosure',kamaec:'inside','⿵A':'upper enclosure','⿵B':'inside','⿶1':'inside','⿶2':'lower enclosure'};
    Object.keys(positions).forEach(k => assert.equal(renderer.position({position:k}), positions[k]));
    assert.equal(renderer.position({position:'unknown'}), '');
    assert.equal(renderer.position({position:'left',via:[{position:'right'}]}), 'left');
    assert.equal(renderer.position({via:[{position:'nyoc'}]}), 'inside');
    assert.equal(renderer.position({via:[{position:'left'},{position:'left'}]}), '');
    assert.equal(renderer.position({via:[{},{position:'left'}]}), '');
});
test('payload strings remain data', () => {
    const payload = {version:1,entries:[{char:'人',meanings:['</script><img src=x onerror=alert(1)>']} ]};
    assert.deepEqual(renderer.parse(JSON.stringify(payload)), payload);
});
console.log(`${tests} formatter tests passed`);

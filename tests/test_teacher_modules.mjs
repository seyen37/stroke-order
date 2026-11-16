// v0.14.301 R2 — static/teacher/{dictcard,player}.mjs 純邏輯。
// node --test tests/test_teacher_modules.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { esc, parseSenses, sensesHtml, firstExample }
  from '../src/stroke_order/web/static/teacher/dictcard.mjs';
import { glyphSvg, playerSvg, SPEEDS }
  from '../src/stroke_order/web/static/teacher/player.mjs';

const YUAN = '1.種植花木、蔬果的地方。[例]果園、菜園、茶園\n' +
  '2.供人遊覽、休憩的地方。[例]公園、遊樂園、動物園\n3.帝王、后妃的墓地。[例]陵園、園廟';

test('parseSenses：依編號切義項、依第一個 [例] 分釋義與例句', () => {
  const s = parseSenses(YUAN);
  assert.equal(s.length, 3);
  assert.deepEqual(s[0], { n: '1', text: '種植花木、蔬果的地方。', ex: '果園、菜園、茶園' });
  assert.equal(s[2].n, '3');
});

test('parseSenses：CC BY-ND 不改寫——除切分記號外文字逐字守恆', () => {
  const HAO10 = '10. 嘆詞：(1) 表示稱讚或允許的語氣。[例]好！正合我意！　(2) 表示責備或不滿的語氣。[例] 好了！我已聽夠了！';
  const [s] = parseSenses(HAO10);
  assert.equal(s.n, '10');
  assert.equal(s.text, '嘆詞：(1) 表示稱讚或允許的語氣。');
  assert.ok(s.ex.includes('(2) 表示責備或不滿的語氣。[例] 好了！'), '後續 [例] 原樣保留');
  const strip = x => x.replace(/\s+/g, '');
  for (const def of [YUAN, HAO10]) {
    const joined = parseSenses(def).map(v =>
      (v.n ? v.n + '.' : '') + v.text + (v.ex ? '[例]' + v.ex : '')).join('');
    assert.equal(strip(joined), strip(def));
  }
});

test('parseSenses：無編號（老師自填）→ 單一義項；續行併入不丟字', () => {
  assert.deepEqual(parseSenses('自己寫的說明'), [{ n: '', text: '自己寫的說明', ex: '' }]);
  const s = parseSenses('1.第一義\n補充一行\n2.第二義');
  assert.equal(s.length, 2);
  assert.equal(s[0].text, '第一義 補充一行');
  assert.deepEqual(parseSenses(''), []);
  assert.deepEqual(parseSenses(null), []);
});

test('sensesHtml：.t-sense 卡、例句 .ex、XSS 跳脫', () => {
  const h = sensesHtml(YUAN);
  assert.equal((h.match(/class="t-sense"/g) || []).length, 3);
  assert.ok(h.includes('<div class="ex"><span class="lab">例</span>果園、菜園、茶園</div>'));
  assert.ok(!sensesHtml('<img src=x onerror=1>').includes('<img'));
  assert.equal(esc(`<a href="x">'&`), '&lt;a href=&quot;x&quot;&gt;&#39;&amp;');
});

test('firstExample：取句子、頓號例詞串不當句子', () => {
  assert.equal(firstExample('種植花木果蔬的地方。[例]那塊園圃所種的玫瑰正盛開著。'),
               '那塊園圃所種的玫瑰正盛開著。');
  assert.equal(firstExample('[例]果園、菜園'), '');
  assert.equal(firstExample(''), '');
});

test('glyphSvg／playerSvg：hanzi-writer 座標翻轉、兩層同筆數', () => {
  const st = ['M 0 0 L 10 10', 'M 5 5 L 9 9'];
  const g = glyphSvg(st);
  assert.ok(g.includes('translate(0, 900) scale(1, -1)'));
  assert.equal((g.match(/<path /g) || []).length, 2);
  const p = playerSvg(st);
  assert.ok(p.includes('class="ghost"') && p.includes('class="ink"'));
  assert.equal((p.match(/<path /g) || []).length, 4);
  assert.equal(glyphSvg(null).includes('<path'), false);
});

test('SPEEDS：慢 > 中 > 快', () => {
  assert.ok(SPEEDS.slow > SPEEDS.normal && SPEEDS.normal > SPEEDS.fast);
});

// ---- v0.14.302 R3：classcore.mjs ----
import { MAX_CHARS, MIN_GRID_COLUMNS, parseQuery, gridChars, gridUrl, stepsUrl, stepsCols, findWord }
  from '../src/stroke_order/web/static/teacher/classcore.mjs';

test('parseQuery：只留漢字、保留疊字、擴充區不拆、上限', () => {
  assert.deepEqual(parseQuery(' 好 朋友！ab1'), ['好', '朋', '友']);
  assert.deepEqual(parseQuery('天天'), ['天', '天']);
  assert.deepEqual(parseQuery('𪚥'), ['𪚥']);
  assert.equal(parseQuery('一'.repeat(30)).length, MAX_CHARS);
  assert.deepEqual(parseQuery(null), []);
});

test('gridUrl／stepsUrl：參數正確、中文編碼、svg 不帶 download', () => {
  const g = new URL(gridUrl('花園'), 'http://x');
  assert.equal(g.pathname, '/api/grid');
  assert.equal(g.searchParams.get('chars'), '花園花園花園');
  assert.equal(g.searchParams.get('format'), 'pdf');
  assert.equal(g.searchParams.get('guide'), 'mi');
  const s = new URL(stepsUrl('園', 'svg'), 'http://x');
  assert.equal(s.pathname, '/api/steps');
  assert.equal(s.searchParams.get('download'), null);
  assert.equal(new URL(stepsUrl('園', 'pdf'), 'http://x').searchParams.get('download'), 'true');
});

test('findWord：整詞比對、查無回 null、未收字回 null', () => {
  const d = { found: true, words: [{ word: '花園', definition: 'x' }, { word: '花' }] };
  assert.equal(findWord(d, '花園').definition, 'x');
  assert.equal(findWord(d, '花園子'), null);
  assert.equal(findWord({ found: false }, '花園'), null);
  assert.equal(findWord(null, '花園'), null);
});

test('stepsCols：跟筆畫數、夾 4–10', () => {
  assert.equal(stepsCols(9), 9);
  assert.equal(stepsCols(2), 4);
  assert.equal(stepsCols(23), 10);
  assert.equal(stepsCols(undefined), 4);
  assert.equal(new URL(stepsUrl('春', 'svg', 9), 'http://x').searchParams.get('cols'), '9');
});

test('gridChars：補滿至少 6 行、詞序不亂、長詞不截', () => {
  assert.equal(MIN_GRID_COLUMNS, 6);
  assert.equal(gridChars('學'), '學學學學學學');
  assert.equal(gridChars('春天'), '春天春天春天');
  assert.equal(gridChars('好朋友'), '好朋友好朋友');
  assert.equal(gridChars('一二三四五六七'), '一二三四五六七');
  assert.equal(gridChars(''), '');
  assert.ok(gridChars('一'.repeat(MAX_CHARS)).length <= 40);   // /api/grid 上限
});

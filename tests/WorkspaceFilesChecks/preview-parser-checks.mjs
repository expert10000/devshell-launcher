import assert from 'node:assert/strict';
import { parseDelimited, parseJsonPreview } from '../../DevShell/ui/dev-ui-react/src/filePreviewParsers.ts';

function check(label, run) { run(); console.log(`PASS: ${label}`); }
check('CSV quoted commas and escaped quotes', () => assert.deepEqual(parseDelimited('name,value\n"a,b","say ""hello"""\n', ',').rows, [['name', 'value'], ['a,b', 'say "hello"']]));
check('CSV quoted multiline fields', () => assert.deepEqual(parseDelimited('a,b\n"line1\nline2",x', ',').rows, [['a', 'b'], ['line1\nline2', 'x']]));
check('TSV and CRLF parsing', () => assert.deepEqual(parseDelimited('a\tb\r\n1\t2\r\n', '\t').rows, [['a', 'b'], ['1', '2']]));
check('CSV trailing empty cell', () => assert.deepEqual(parseDelimited('a,b,', ',').rows, [['a', 'b', '']]));
check('Table row limit', () => { const result = parseDelimited('a\n1\n2\n3\n', ',', 2); assert.equal(result.rows.length, 2); assert.equal(result.truncated, true); });
check('Table column limit', () => { const result = parseDelimited('a,b,c', ',', 10, 2); assert.deepEqual(result.rows, [['a', 'b']]); assert.equal(result.truncated, true); });
check('Table cell limit', () => { const result = parseDelimited('abcdef', ',', 10, 2, 3); assert.deepEqual(result.rows, [['abc']]); assert.equal(result.truncated, true); });
check('Incomplete quoted field warning', () => assert.ok(parseDelimited('a\n"unfinished', ',').warning));
check('Valid JSON primitive', () => assert.equal(parseJsonPreview('null').value, null));
check('Invalid JSON is reported without execution', () => assert.ok(parseJsonPreview('{"unfinished":').error));
check('Prototype-shaped JSON remains plain data', () => { const value = parseJsonPreview('{"__proto__":{"polluted":true}}').value; assert.equal(Object.hasOwn(value, '__proto__'), true); assert.equal({}.polluted, undefined); });

// Run with: node --test tests/test_job_client.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../static/js/job.js'), 'utf8');
const settle = () => new Promise(resolve => setImmediate(resolve));

function browser(status = 'running', replies = []) {
  const ids = ['jobCard', 'jobTitle', 'jobMessage', 'jobSpinner', 'jobProgress',
    'jobProgressWrap', 'jobStage', 'jobPercent', 'jobSample', 'jobEyebrow', 'jobBackgroundNote'];
  const elements = Object.fromEntries(ids.map(id => [id, {
    textContent: '', hidden: false, dataset: {},
    classList: { add() {} },
  }]));
  elements.jobCard.dataset = { jobStatus: status, jobId: 'job1', apiUrl: '/api/jobs/job1', jobUrl: '/jobs/job1' };
  elements.jobSample.hidden = status !== 'failed';
  elements.jobMessage.textContent = 'โมเดลขัดข้อง';
  const timers = new Map();
  let nextTimer = 0;
  const calls = [];
  const redirects = [];
  const context = {
    AbortController,
    document: { hidden: false, getElementById: id => elements[id], addEventListener() {} },
    window: { analysisTracker: { track() {}, clear() {} } },
    location: { assign: url => redirects.push(url) },
    setTimeout: (callback, delay) => { const id = ++nextTimer; timers.set(id, { callback, delay }); return id; },
    clearTimeout: id => timers.delete(id),
    fetch: async (url, options) => {
      calls.push({ url, options });
      const reply = replies.shift();
      if (reply instanceof Error) throw reply;
      return { ok: true, json: async () => reply };
    },
  };
  vm.runInNewContext(source, context);
  return { elements, timers, calls, redirects };
}

test('an already failed job offers the example without a status request', () => {
  const state = browser('failed');
  assert.equal(state.elements.jobSample.hidden, false);
  assert.equal(state.elements.jobMessage.textContent, 'โมเดลขัดข้อง');
  assert.equal(state.calls.length, 0);
  assert.equal(state.timers.size, 0);
});

test('failure during polling reveals the example and stops polling', async () => {
  const state = browser('running', [{ status: 'failed', error_message: 'ดึงรีวิวไม่ได้' }]);
  await settle();
  assert.equal(state.elements.jobSample.hidden, false);
  assert.equal(state.elements.jobMessage.textContent, 'ดึงรีวิวไม่ได้');
  assert.equal(state.timers.size, 0);
});

test('connection errors offer the example but a recovered job continues normally', async () => {
  const state = browser('running', [new Error('connection lost'), { status: 'running', progress: 65, stage: 'aspects' }]);
  await settle();
  assert.equal(state.elements.jobSample.hidden, false);
  assert.equal(state.elements.jobTitle.textContent, 'การเชื่อมต่อขัดข้องชั่วคราว');
  const [id, timer] = [...state.timers][0];
  state.timers.delete(id);
  await timer.callback();
  assert.equal(state.elements.jobSample.hidden, true);
  assert.equal(state.elements.jobProgress.value, 65);
  assert.equal(state.elements.jobTitle.textContent, 'กำลังวิเคราะห์รีวิว');
  assert.ok(state.calls[0].options.signal instanceof AbortSignal);
});

test('successful jobs still redirect to their own result', async () => {
  const state = browser('running', [{ status: 'completed', analysis_id: 42, dashboard_url: '/dashboard/42' }]);
  await settle();
  assert.deepEqual(state.redirects, ['/dashboard/42']);
  assert.equal(state.elements.jobSample.hidden, true);
  assert.equal(state.timers.size, 0);
});

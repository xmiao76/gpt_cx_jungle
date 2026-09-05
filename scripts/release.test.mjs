import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { guardedRollback, deploymentSummary } from './pages.mjs';
import { timingSummary } from './timing-cases.mjs';

test('failed production verification restores only our own deployment', async () => {
  let active = { id: 'new' };
  const result = await guardedRollback({ id: 'old' }, { id: 'new' }, async () => active, async id => { active = { id }; });
  assert.deepEqual(result, { restored: true, id: 'old' });
  assert.equal(active.id, 'old');
});
test('rollback does not overwrite an independent deployment', async () => {
  const result = await guardedRollback({ id: 'old' }, { id: 'ours' }, async () => ({ id: 'someone-else' }), async () => assert.fail('Unexpected rollback'));
  assert.equal(result.restored, false);
});
test('first deployment and unidentified promotions cannot trigger a rollback', async () => {
  const current = async () => ({ id: 'new' });
  const restore = async () => assert.fail('Unexpected rollback');
  assert.equal((await guardedRollback(null, { id: 'new' }, current, restore)).restored, false);
  assert.equal((await guardedRollback({ id: 'old' }, null, current, restore)).restored, false);
});
test('a failed rollback cannot be reported as successful', async () => {
  await assert.rejects(guardedRollback({ id: 'old' }, { id: 'new' }, async () => ({ id: 'new' }), async () => {}), /did not restore/);
});
test('timing reports use the arithmetic median for an even sample count', () => {
  const samples=['easy','medium','hard'].flatMap(difficulty=>Array.from({length:10},(_,index)=>({difficulty,responseMs:index+1})));
  const report=timingSummary('test',samples);
  assert.equal(report.difficulties.easy.medianMs,5.5);
  assert.equal(report.difficulties.easy.p95Ms,10);
  assert.equal(report.passed,true);
});
test('deployment evidence excludes environment values and unrelated account data', () => {
  const summary=deploymentSummary({id:'release-id',url:'https://test.pages.dev',env_vars:{PRIVATE:{type:'secret_text',value:'do-not-record'}},account:{name:'private-account'},latest_stage:{status:'success'},deployment_trigger:{metadata:{branch:'main',commit_message:'release'}}});
  assert.equal(summary.id,'release-id');
  assert.equal(summary.deployment_trigger.metadata.branch,'main');
  assert.equal(JSON.stringify(summary).includes('do-not-record'),false);
  assert.equal('env_vars' in summary,false);
  assert.equal('account' in summary,false);
});
test('an absent previous deployment stays absent', () => {
  assert.equal(deploymentSummary(null),null);
});

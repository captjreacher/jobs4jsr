import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from jobs4jsr import coordinator,poller,cli,database
import test_discovery_integration as fixtures

class UpdateTests(unittest.TestCase):
    setUp=fixtures.IntegrationTests.setUp
    tearDown=fixtures.IntegrationTests.tearDown
    job=fixtures.IntegrationTests.job
    invoke=fixtures.IntegrationTests.invoke
    connect=fixtures.IntegrationTests.connect

    def test_process_gate_defers_scheduled_slot_without_losing_it(self):
        program="""import sys;from pathlib import Path;from jobs4jsr import coordinator
root=Path(sys.argv[1])
with coordinator.command(root,'scheduled','2026-10-20-scheduled') as acquired:
 assert not acquired
"""
        with coordinator.execution_lock(self.root):
            result=subprocess.run([sys.executable,'-c',program,str(self.root)],capture_output=True,text=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stderr)
            with coordinator.execution_lock(self.root):pass  # reentrant only in this thread
        self.assertEqual(coordinator.next_slot(self.root),'2026-10-20-scheduled')
        with coordinator.command(self.root,'scheduled','2026-10-20-scheduled') as acquired:self.assertTrue(acquired)
        self.assertIsNone(coordinator.next_slot(self.root))

    def test_checkpoint_recovers_failed_publication_without_rediscovery(self):
        with patch('jobs4jsr.cli.sync.configured',return_value=True),patch('jobs4jsr.cli.sync.publish',side_effect=RuntimeError('failure')):
            with self.assertRaises(RuntimeError):self.invoke([self.job(1)],[],'search','--run-id','recovery')
        c=self.connect();ident=database.jobs(c)[0]['stable_id'];c.close()
        with patch('jobs4jsr.cli.sync.configured',return_value=True),patch('jobs4jsr.cli.sync.publish') as publish,patch('jobs4jsr.cli.discovery.discover') as discover:
            cli.main(['--root',str(self.root),'search','--run-id','recovery'])
            discover.assert_not_called();self.assertEqual(publish.call_args.kwargs['summary']['new_jobs'],1)
        c=self.connect();self.assertEqual(database.jobs(c)[0]['stable_id'],ident)
        self.assertEqual(c.execute('select published from update_checkpoints').fetchone()[0],1);c.close()

    def test_unique_existing_refresh_metric_not_source_duplicate_count(self):
        self.invoke([self.job(1)],[],'search','--run-id','first')
        alt=dict(self.job(1),source='Alternate',url='https://alternate.example/1')
        self.invoke([self.job(1),alt],[],'search','--run-id','second')
        c=self.connect();summary=json.loads(c.execute("select summary from update_checkpoints where run_id='manual-second'").fetchone()[0]);c.close()
        self.assertEqual(summary['new_jobs'],0);self.assertEqual(summary['refreshed_jobs'],1)

    def test_guard_kills_on_timeout_or_unconfirmed_lease_loss_not_terminal_ack_loss(self):
        killed=[]
        with patch('jobs4jsr.poller.time.monotonic',return_value=0):guard=poller.Guard(Mock(side_effect=OSError()),abort=killed.append)
        with patch('jobs4jsr.poller.time.monotonic',return_value=91):guard.check()
        self.assertEqual(killed,[75])
        killed.clear();guard.terminal=lambda:True
        with patch('jobs4jsr.poller.time.monotonic',return_value=92):guard.check()
        self.assertEqual(killed,[]);self.assertTrue(guard.stopped.is_set())
        with patch('jobs4jsr.poller.time.monotonic',return_value=1201):guard.check()
        self.assertEqual(killed,[75])

    def test_crash_pending_slot_recovered_and_repeated_failures_are_visible(self):
        coordinator.defer(self.root,'2026-10-20-scheduled')
        with coordinator.control(self.root) as c:c.execute("update deferred_slots set state='running'")
        self.assertEqual(coordinator.next_slot(self.root),'2026-10-20-scheduled')
        for _ in range(3):
            with self.assertRaises(ValueError):
                with coordinator.command(self.root,'scheduled','2026-10-20-scheduled'):raise ValueError('failed')
        self.assertIsNone(coordinator.next_slot(self.root))
        with coordinator.control(self.root) as c:
            self.assertEqual(c.execute('select state,error from deferred_slots').fetchone(),('failed','scheduled_run_failed'))

    def test_poller_prioritises_deferred_schedule_before_claim(self):
        coordinator.defer(self.root,'2026-10-20-scheduled');api=Mock()
        with patch('jobs4jsr.poller.cli.main') as execute:
            poller.tick(self.root,api)
        self.assertIn('--slot',execute.call_args.args[0])
        self.assertFalse(any(call.args[0]=='claim_update' for call in api.rpc.call_args_list))

    def test_ack_loss_reconciles_checkpoint_and_failure_requeues(self):
        c=self.connect();c.execute("insert into update_checkpoints values('manual-update-test','{}',0)");c.commit();c.close()
        api=Mock();api.request.return_value={'state':'completed','summary':{'new_jobs':0}}
        poller.reconcile_publications(self.root,api)
        c=self.connect();self.assertEqual(c.execute('select published from update_checkpoints').fetchone()[0],1);c.close()
        api=Mock();api.rpc.side_effect=lambda name,**args: {'id':'fixture','claim_token':'token'} if name=='claim_update' else True
        api.request.return_value={'state':'running','summary':None}
        with patch('jobs4jsr.poller.cli.main',side_effect=RuntimeError()):poller.tick(self.root,api)
        self.assertTrue(any(call.args[0]=='fail_update' for call in api.rpc.call_args_list))

    def test_scheduled_publication_recovery_preserves_source_failure_exit_code(self):
        c=self.connect()
        c.execute("insert into update_checkpoints values('2026-10-20-scheduled',?,0)",(json.dumps({'new_jobs':0,'refreshed_jobs':1,'source_failures':['Employer A']}),));c.commit();c.close()
        with patch('jobs4jsr.cli.sync.configured',return_value=True),patch('jobs4jsr.cli.sync.publish'),patch('jobs4jsr.cli.discovery.discover') as discover:
            with self.assertRaises(SystemExit) as caught:cli.main(['--root',str(self.root),'scheduled','--slot','2026-10-20-scheduled'])
            self.assertEqual(caught.exception.code,2);discover.assert_not_called()
        self.assertIsNotNone(coordinator.control)
        with coordinator.control(self.root) as c:self.assertEqual(c.execute('select state from deferred_slots').fetchone()[0],'queued')

    def test_poller_is_disabled_before_any_network_or_discovery(self):
        with patch.object(sys,'argv',['poller','--root',str(self.root),'--once']),patch.dict(os.environ,{},clear=True),patch('jobs4jsr.poller.API') as api:
            with self.assertRaisesRegex(RuntimeError,'Poller disabled'):poller.main()
            api.assert_not_called()

    def test_watchdog_deadline_is_independent_of_heartbeat_http(self):
        aborted=[]
        with patch('jobs4jsr.poller.time.monotonic',return_value=0):guard=poller.Guard(Mock(),abort=aborted.append)
        with patch('jobs4jsr.poller.time.monotonic',return_value=1201):guard.watch()
        self.assertEqual(aborted,[75]);guard.heartbeat.assert_not_called()

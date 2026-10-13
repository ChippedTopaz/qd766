import unittest,importlib.util,io,json
from pathlib import Path
from unittest.mock import patch,MagicMock
from contextlib import redirect_stdout
ROOT=Path(__file__).resolve().parents[1]

class WorkerServiceRecoveryTests(unittest.TestCase):
 def test_unexpected_worker_failure_exits_nonzero_without_secrets(self):
  spec=importlib.util.spec_from_file_location('worker_service_recovery_test',ROOT/'tools/run_collection_worker.py')
  module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  engine=MagicMock();output=io.StringIO()
  with patch.object(module.sys,'argv',['worker','--once']),patch.object(module,'load_environment_file'),\
       patch.object(module.Settings,'from_env',return_value=MagicMock()),patch.object(module,'create_database_engine',return_value=engine),\
       patch.object(module,'create_session_factory'),patch.object(module,'UrllibTransport'),patch.object(module,'EvaluationSnapshotProcessor'),\
       patch.object(module,'run_one_job',side_effect=RuntimeError('password=DO_NOT_LOG')),redirect_stdout(output):
   self.assertEqual(module.main(),1)
  events=[json.loads(line) for line in output.getvalue().splitlines()]
  self.assertEqual(events[0]['event'],'worker-started');self.assertGreater(events[0]['pid'],0)
  self.assertEqual(events[-1]['event'],'worker-fatal');self.assertEqual(events[-1]['errorType'],'RuntimeError')
  self.assertNotIn('DO_NOT_LOG',output.getvalue());engine.dispose.assert_called_once()
 def test_supervisor_and_keepalive_are_non_destructive_and_idempotent(self):
  supervisor=(ROOT/'tools/start_controlled_worker.ps1').read_text(encoding='utf-8')
  hardening=(ROOT/'tools/harden_collection_worker_task.ps1').read_text(encoding='utf-8')
  self.assertIn('while ($true)',supervisor);self.assertIn('worker-supervisor-restart',supervisor)
  self.assertIn('[Math]::Min(60',supervisor);self.assertIn('--controlled',supervisor)
  self.assertNotIn('Stop-Process',supervisor);self.assertNotIn('requeue_expired_jobs(',supervisor)
  self.assertIn('$Task.Actions.Count -ne 1',hardening);self.assertIn('Export-ScheduledTask',hardening)
  self.assertIn("$_.Id -eq 'QD766WorkerKeepAlive'",hardening)
  self.assertIn('New-TimeSpan -Minutes 2',hardening);self.assertIn('$Settings.MultipleInstances = 2',hardening)
  self.assertNotIn('Stop-ScheduledTask',hardening);self.assertNotIn('Start-ScheduledTask',hardening)
  self.assertNotIn('Remove-ScheduledTask',hardening)
 def test_controlled_release_keeps_one_job_three_threads_without_watchdog(self):
  spec=importlib.util.spec_from_file_location('worker_sequential_release_test',ROOT/'tools/run_collection_worker.py')
  module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  engine=MagicMock();transport=MagicMock();output=io.StringIO()
  with patch.object(module.sys,'argv',['worker','--controlled','--once']),patch.object(module,'load_environment_file'),\
       patch.object(module.Settings,'from_env',return_value=MagicMock()),patch.object(module,'create_database_engine',return_value=engine),\
       patch.object(module,'create_session_factory'),patch('qd766.concurrent_collection.PooledHttpTransport',return_value=transport) as pooled,\
       patch.object(module,'EvaluationSnapshotProcessor') as processor,patch.object(module,'run_one_job',return_value=None) as run,redirect_stdout(output):
   self.assertEqual(module.main(),0)
  self.assertEqual(run.call_count,1)
  self.assertEqual(pooled.call_args.kwargs['max_workers'],3)
  self.assertEqual(processor.call_args.kwargs['max_workers'],3)
  self.assertEqual(processor.call_args.kwargs['max_retries'],4)
  transport.close.assert_called_once();engine.dispose.assert_called_once()
  for relative in ('tools/run_collection_worker.py','tools/start_controlled_worker.ps1','tools/restart_collection_worker.ps1'):
   source=(ROOT/relative).read_text(encoding='utf-8')
   for excluded in ('supervised_worker','parallel_worker','parallel_runner','parallel_transport','job_watchdog','QD766_WORKER_JOBS'):
    self.assertNotIn(excluded,source)
 def test_paused_source_restart_requires_empty_queue_and_preserves_circuit(self):
  source=(ROOT/'tools/restart_collection_worker.ps1').read_text(encoding='utf-8')
  self.assertEqual(source.count("$Health.status -notin @('IDLE','SAFETY_PAUSED')"),2)
  self.assertEqual(source.count('$Health.queued -ne 0 -or $Health.running -ne 0'),2)
  self.assertNotIn('reset_collection_circuit',source)
  self.assertNotIn('open_collection_circuit',source)
  self.assertNotIn('UPDATE collection_controls',source)

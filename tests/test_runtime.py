import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from agent_runtime import (
    AutomationError, Event, FixtureSource, FileDestination, Store, TelegramDestination,
    GithubIssueSource, OpenAICompatibleModel, evaluate, run,
)


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.events = self.root / 'events.json'
        self.database = self.root / 'state.sqlite3'
        self.out = self.root / 'briefs.jsonl'
        self.config = dict(agent_id='demo', timezone='Europe/Moscow', state_db=str(self.database),
                           sources=[{'type': 'fixture', 'name': 'demo', 'path': str(self.events)}],
                           destination={'type': 'file', 'path': str(self.out)})
        self.write_events([dict(id='1', title='New task', url='https://example.test/1',
                                updated_at='2026-10-13T00:00:00Z', state='open')])

    def write_events(self, events):
        self.events.write_text(json.dumps(events), encoding='utf-8')

    def test_dry_run_does_not_publish_or_move_cursor(self):
        _, cursors, events, errors = run(self.config, dry_run=True)
        self.assertEqual(len(events), 1)
        self.assertFalse(self.out.exists())
        self.assertEqual(Store(self.database).cursor('demo'), '')

    def test_delivery_and_idempotence(self):
        run(self.config, dry_run=False)
        self.assertEqual(len(self.out.read_text().splitlines()), 1)
        run(self.config, dry_run=False)
        self.assertEqual(len(self.out.read_text().splitlines()), 1)
        self.assertEqual(Store(self.database).cursor('demo'), '2026-10-13T00:00:00Z')

    def test_update_can_republish(self):
        run(self.config, dry_run=False)
        self.write_events([dict(id='1', title='Task updated', url='https://example.test/1', updated_at='2026-10-13T02:00:00Z')])
        run(self.config, dry_run=False)
        self.assertEqual(len(self.out.read_text().splitlines()), 2)

    def test_closed_event_does_not_publish(self):
        self.write_events([dict(id='1', title='Closed', url='https://example.test/1', updated_at='2026-10-13T00:00:00Z', state='closed')])
        run(self.config, dry_run=False)
        self.assertFalse(self.out.exists())
        self.assertEqual(Store(self.database).cursor('demo'), '2026-10-13T00:00:00Z')

    def test_unavailable_source_does_not_move_cursor_and_is_reported(self):
        self.events.unlink()
        report, cursors, events, errors = run(self.config, dry_run=False)
        self.assertEqual(len(errors), 1)
        self.assertIn('Не удалось проверить', report)
        self.assertEqual(Store(self.database).cursor('demo'), '')

    def test_ambiguous_delivery_blocks_until_reconciled(self):
        with patch.object(FileDestination, 'post', side_effect=AutomationError('timeout')):
            with self.assertRaises(AutomationError):
                run(self.config, dry_run=False)
        store = Store(self.database)
        self.assertEqual(store.outstanding()[2], 'maybe_posted')
        self.assertEqual(store.cursor('demo'), '')
        with self.assertRaises(AutomationError):
            run(self.config, dry_run=False)

    def test_crash_after_send_can_be_reconciled_from_outbox(self):
        original = Store.finalize
        with patch.object(Store, 'finalize', side_effect=RuntimeError('crash')):
            with self.assertRaises(RuntimeError):
                run(self.config, dry_run=False)
        self.assertEqual(Store(self.database).outstanding()[2], 'posting')
        self.assertEqual(len(self.out.read_text().splitlines()), 1)
        # Operator uses reconcile command after ensuring no running worker.
        from agent_runtime import main
        config_path = self.root / 'config.json'
        config_path.write_text(json.dumps(self.config), encoding='utf-8')
        self.assertEqual(main(['reconcile', '--config', str(config_path)]), 0)
        self.assertIsNone(Store(self.database).outstanding())
        self.assertEqual(Store(self.database).cursor('demo'), '2026-10-13T00:00:00Z')
        run(self.config, dry_run=False)
        self.assertEqual(len(self.out.read_text().splitlines()), 1)

    def test_lock_requires_manual_reset(self):
        store = Store(self.database)
        store.acquire('another-worker')
        with self.assertRaises(AutomationError):
            run(self.config, dry_run=False)

    def test_max_events_rejects_without_checkpoint(self):
        self.config['max_events_per_run'] = 1
        self.write_events([{'id': str(i), 'title': str(i), 'url': f'https://example.test/{i}', 'updated_at': '2026-10-13T00:00:00Z'} for i in range(3)])
        _, cursors, events, errors = run(self.config, dry_run=False)
        self.assertEqual(len(errors), 1)
        self.assertNotIn('demo', cursors)
        self.assertEqual(Store(self.database).cursor('demo'), '')

    def test_cursor_unchanged_if_verify_fails(self):
        class Bad(FixtureSource):
            def verify(self, item):
                raise AutomationError('Unavailable')
        store = Store(self.database)
        _, cursors, events, errors = evaluate([Bad('demo', self.events)], store, 30, None)
        self.assertEqual(cursors, {})
        self.assertEqual(events, [])
        self.assertTrue(errors)

    def test_model_requires_explicit_price_and_https(self):
        with self.assertRaises(AutomationError):
            OpenAICompatibleModel({'model':'x','base_url':'http://example.com','max_run_usd':1,'usd_per_million_input_tokens':1,'usd_per_million_output_tokens':1})
        with self.assertRaises(AutomationError):
            OpenAICompatibleModel({'model':'x','base_url':'https://example.com'})

    def test_github_requires_token(self):
        src = GithubIssueSource('org/repo', token_env='MISSING_UNIT_TEST_GITHUB_TOKEN')
        with self.assertRaises(AutomationError):
            src.read('')

    def test_telegram_no_reconciliation_by_assumption(self):
        self.assertIsNone(TelegramDestination('42').lookup('edition'))


if __name__ == '__main__':
    unittest.main()

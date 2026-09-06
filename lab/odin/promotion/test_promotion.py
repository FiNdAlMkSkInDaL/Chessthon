"""Small tests proving incomplete/mismatched evidence cannot reach copying."""
from copy import deepcopy
import io
from pathlib import Path
import tempfile
import unittest
import zipfile

import chess

from lab.odin.promotion.promote import (
    PACKAGES,STORM_SHA,V3_SHA,apply_bytes,inspect_archive,sha,validate_contract,validate_gate,
)


def archive_bytes(extra=None,create_system=3):
    members={'agent.py':b'def get_move(fen, time_left_ms):\n    return "a2a3"\n'}
    if extra:
        members.update(extra)
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for name,payload in members.items():
            info=zipfile.ZipInfo(name)
            info.create_system=create_system
            info.external_attr=0o100644<<16
            archive.writestr(info,payload)
    return buffer.getvalue(),members


def frozen_plan():
    openings=[]
    for fullmove in range(1,41):
        b=chess.Board()
        b.fullmove_number=fullmove
        openings.append(b.fen())
    plan={'schema_version':1,'base_ms':120000,'increment_ms':500,'init_budget_s':90.,'ply_cap':600,
          'packages':PACKAGES,'source_provenance':{'official/harness/referee.py':'d'*64},'suites':{}}
    for name,count,criterion,baseline in [('primary',40,'paired_ci_lower','b'*64),('guard',16,'raw_score',STORM_SHA)]:
        plan['suites'][name]={'candidate_sha256':'a'*64,'baseline_sha256':baseline,'openings_sha256':'c'*64,
                             'openings':openings[:count],'min_pairs':count,'criterion':criterion,'threshold':.5,
                             'lanes':[{'id':'a','cpu':0,'opening_indices':list(range(count))}]}
    return plan


def incomplete_gate(ready):
    return {'verdict':'PASS','archive':{'sha256':'a'*64,'private_snapshot_verified':True,'entries':[]},
            'runtime':{'python':'3.12.3','machine':'x86_64','platform':'Linux-test','packages':PACKAGES,
                       'cpu_models':['test']},'source_provenance':{'official/harness/referee.py':'d'*64},
            'service_runtime_limit_s':900,'odin_rules_required':True,
            'structural':{'verdict':'PASS','original_numba_ready':ready,'nopython_root_signatures':['test'],
                          'cold_agent_import_s':30.},'protocol':{'cold_agent_import_s':30.}}


class PromotionTests(unittest.TestCase):
    def test_exact_readable_source_passes_and_mismatch_fails(self):
        raw,members=archive_bytes()
        with tempfile.TemporaryDirectory() as temporary:
            source=Path(temporary)
            for name,payload in members.items():
                (source/name).write_bytes(payload)
            self.assertEqual(inspect_archive(raw,source)['sha256'],sha(raw))
            (source/'agent.py').write_bytes(b'# changed\n')
            with self.assertRaisesRegex(ValueError,'differs'):
                inspect_archive(raw,source)

    def test_non_source_asset_rejected(self):
        raw,members=archive_bytes({'weights.bin':b'no'})
        with tempfile.TemporaryDirectory() as temporary:
            source=Path(temporary)
            for name,payload in members.items():
                (source/name).write_bytes(payload)
            with self.assertRaisesRegex(ValueError,'flat Python'):
                inspect_archive(raw,source)

    def test_non_unix_zip_rejected(self):
        raw,members=archive_bytes(create_system=0)
        with tempfile.TemporaryDirectory() as temporary:
            source=Path(temporary)
            for name,payload in members.items():
                (source/name).write_bytes(payload)
            with self.assertRaisesRegex(ValueError,'Unix'):
                inspect_archive(raw,source)

    def test_original_ready_false_and_missing_perft_rejected(self):
        plan=frozen_plan()
        manifest={'sha256':'a'*64,'entries':[]}
        with self.assertRaisesRegex(ValueError,'native ready'):
            validate_gate(incomplete_gate(False),manifest,plan)
        with self.assertRaisesRegex(ValueError,'perft'):
            validate_gate(incomplete_gate(True),manifest,plan)

    def test_gate_wrong_zip_rejected(self):
        with self.assertRaisesRegex(ValueError,'different ZIP'):
            validate_gate(incomplete_gate(True),{'sha256':'f'*64,'entries':[]},frozen_plan())

    def test_required_complete_counts_and_guard_criterion(self):
        plan=frozen_plan()
        validate_contract(plan,'a'*64)
        for mutation in ('count','guard_criterion','guard_archive'):
            changed=deepcopy(plan)
            if mutation=='count':
                changed['suites']['primary']['min_pairs']=39
            elif mutation=='guard_criterion':
                changed['suites']['guard']['criterion']='paired_ci_lower'
            else:
                changed['suites']['guard']['baseline_sha256']=V3_SHA
            with self.assertRaises(ValueError):
                validate_contract(changed,'a'*64)

    def test_failed_report_and_changed_bytes_cannot_copy(self):
        with tempfile.TemporaryDirectory() as temporary:
            desktop=Path(temporary)
            target=desktop/'agent.zip'
            target.write_bytes(b'untouched')
            for report in ({'verdict':'FAIL'}, {'verdict':'PASS','candidate':{'sha256':'a'*64}}):
                with self.assertRaises(ValueError):
                    apply_bytes(b'unvalidated',report,desktop)
                self.assertEqual(target.read_bytes(),b'untouched')
                self.assertFalse((desktop/'Odin-v5.zip').exists())


if __name__=='__main__':
    unittest.main()

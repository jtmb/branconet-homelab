"""Pure synthetic transition/identity/privacy regressions; no cluster access."""

import copy
from dataclasses import FrozenInstanceError, replace
import importlib.util
from pathlib import Path
import sys
import unittest


SPEC = importlib.util.spec_from_file_location(
    "bortus_restore_completion", Path(__file__).parents[1] / "bortus-restore-completion.py")
completion = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = completion
SPEC.loader.exec_module(completion)

UID = "11111111-1111-1111-1111-111111111111"
OLD_UID = "22222222-2222-2222-2222-222222222222"
BACKUP_UID = "33333333-3333-3333-3333-333333333333"
URL = ("cifs://192.168.0.8/container_backups/k8s-migration-20261009/longhorn"
       "?backup=backup-public-test&volume=pvc-public-original")
EXPECTED = completion.RestoreExpectation(
    "restore-public-test", UID, "longhorn-system", URL,
    completion.BackupIdentity("backup-public-test", "longhorn-system", BACKUP_UID, "backup-rv"),
    OLD_UID, "pvc-public-original", "1073741824")


def event(rv, flags=(True, True), *, event_type="MODIFIED"):
    status = {} if flags is None else dict(zip(("restoreInitiated", "restoreRequired"), flags))
    return {"type": event_type, "object": {
        "apiVersion": completion.API_VERSION, "kind": "Volume",
        "metadata": {"name": EXPECTED.volume_name, "namespace": EXPECTED.namespace,
                     "uid": UID, "resourceVersion": rv},
        "spec": {"fromBackup": URL, "encrypted": True, "numberOfReplicas": 2,
                 "size": "1073741824", "dataEngine": "v1", "standby": False},
        "status": status}}


def trace():
    return [event("initial", None, event_type="ADDED"), event("started"),
            event("finished", (True, False))]


def evaluate(events, expected=EXPECTED, **kwargs):
    options = dict(watch_started_before_create=True, longhorn_version="1.12.1",
                   api_version="longhorn.io/v1beta2")
    options.update(kwargs)
    return completion.evaluate_restore_transition(expected, events, **options)


class RestoreCompletionTests(unittest.TestCase):
    def refuse(self, events, code=None, expected=EXPECTED, **kwargs):
        with self.assertRaises(completion.RestoreTransitionRefused) as caught:
            evaluate(events, expected, **kwargs)
        if code:
            self.assertEqual(code, caught.exception.code)
        self.assertNotIn("PRIVATE_SENTINEL", str(caught.exception))
        return caught.exception

    def test_exact_transition_is_immutable_metadata_only(self):
        events = trace()
        original = copy.deepcopy(events)
        result = evaluate(events)
        self.assertEqual(("started", "finished", "finished"), (
            result.initialized_resource_version, result.completed_resource_version,
            result.last_volume_resource_version))
        self.assertTrue(result.metadata_transition_eligible)
        self.assertIs(result.data_acceptance, False)
        self.assertEqual(EXPECTED.backup, result.backup)
        self.assertEqual(events, original)
        self.assertFalse(hasattr(result, "events"))
        self.assertFalse(hasattr(result, "backup_url"))
        with self.assertRaises(FrozenInstanceError):
            result.volume_uid = OLD_UID

    def test_zero_status_and_absent_initial_flags_are_nonevidence(self):
        events = [event("absent", None, event_type="ADDED"), event("zero", (False, False)),
                  event("restoring"), event("complete", (True, False))]
        self.assertEqual("restoring", evaluate(events).initialized_resource_version)
        del events[0]["object"]["status"]
        self.assertTrue(evaluate(events).metadata_transition_eligible)

    def test_absent_and_false_only_traces_never_complete(self):
        for flags in (None, (False, False)):
            with self.subTest(flags=flags):
                self.refuse([event("zero", flags)], "completion_unobserved")
        self.refuse([event("false", (True, False))], "restore_transition")

    def test_initialization_without_completion_refuses(self):
        self.refuse([event("init"), event("still-restoring")], "completion_unobserved")

    def test_flags_must_be_literal_booleans(self):
        for flags in ((1, True), (True, 0), ("true", True), (None, False), (False, True)):
            with self.subTest(flags=flags):
                self.refuse([event("a", flags), event("b", (True, False))])

    def test_single_missing_flag_is_refused_even_initially(self):
        for missing in ("restoreInitiated", "restoreRequired"):
            events = trace()
            del events[1]["object"]["status"][missing]
            self.refuse(events, "restore_flags")
            events[0]["object"]["status"] = {missing: False}
            self.refuse(events, "restore_flags")

    def test_missing_flags_after_initialization_or_completion_refuse(self):
        self.refuse([event("a"), event("b", None)], "restore_regression")
        self.refuse(trace() + [event("last", None)], "restore_regression")

    def test_regression_after_initialization_and_completion_refuses(self):
        for flags in ((False, False), (False, True)):
            self.refuse([event("a"), event("b", flags)], "restore_regression")
        self.refuse(trace() + [event("last", (True, True))], "restore_regression")

    def test_errors_deletion_gap_markers_never_ignored(self):
        for kind in ("ERROR", "DELETED", "GAP", "PRIVATE_SENTINEL"):
            events = trace() + [{"type": kind, "object": {"message": "PRIVATE_SENTINEL"}}]
            failure = self.refuse(events, "watch_discontinuity")
            self.assertEqual(3, failure.event_index)
        events = trace()
        events[2]["gap"] = True
        self.refuse(events, "event_shape")

    def test_deleted_timestamp_refuses_even_after_completion(self):
        events = trace()
        events[-1]["object"]["metadata"]["deletionTimestamp"] = "public-time"
        self.refuse(events, "volume_deleted")

    def test_identity_drift_anywhere_refuses(self):
        for key, value in (("uid", OLD_UID), ("name", "other"), ("namespace", "other")):
            for position in range(3):
                events = trace()
                events[position]["object"]["metadata"][key] = value
                self.refuse(events, "identity_drift")

    def test_every_spec_fence_is_checked_on_every_event(self):
        for key, value in (("fromBackup", URL + "&token=PRIVATE_SENTINEL"),
                           ("encrypted", False), ("numberOfReplicas", 1),
                           ("numberOfReplicas", True), ("size", "2147483648"),
                           ("size", 1073741824), ("dataEngine", "v2"), ("standby", True)):
            for position in range(3):
                events = trace()
                events[position]["object"]["spec"][key] = value
                self.refuse(events, "spec_drift")

    def test_missing_spec_fields_refuse(self):
        for key in event("a")["object"]["spec"]:
            events = trace()
            del events[1]["object"]["spec"][key]
            self.refuse(events, "spec_shape")

    def test_original_resource_must_be_distinct(self):
        for expected in (replace(EXPECTED, volume_uid=OLD_UID),
                         replace(EXPECTED, volume_name=EXPECTED.original_volume_handle)):
            self.refuse(trace(), "expected_identity", expected)

    def test_backup_identity_and_source_size_required(self):
        for expected in (replace(EXPECTED, source_size_bytes="2147483648"),
                         replace(EXPECTED, backup=replace(EXPECTED.backup, uid="")),
                         replace(EXPECTED, backup=replace(EXPECTED.backup, resource_version="")),
                         replace(EXPECTED, backup=replace(EXPECTED.backup, namespace="other"))):
            self.refuse(trace(), "expected_identity", expected)
        self.refuse(trace(), "source_url", replace(
            EXPECTED, backup=replace(EXPECTED.backup, name="backup-other")))

    def test_exact_url_accepts_query_reordering_but_matches_literal_frombackup(self):
        url = URL.split("?")[0] + "?volume=pvc-public-original&backup=backup-public-test"
        expected = replace(EXPECTED, backup_url=url)
        events = trace()
        for item in events:
            item["object"]["spec"]["fromBackup"] = url
        self.assertTrue(evaluate(events, expected).metadata_transition_eligible)
        events[1]["object"]["spec"]["fromBackup"] = URL
        self.refuse(events, "spec_drift", expected)

    def test_url_blank_duplicate_unknown_queries_refuse(self):
        for suffix in ("&backup=", "&volume=", "&token=", "&backup=backup-public-test",
                       "&PRIVATE_SENTINEL=value", "&", ";token=PRIVATE_SENTINEL"):
            self.refuse(trace(), "source_url", replace(EXPECTED, backup_url=URL + suffix))
        self.refuse(trace(), "source_url", replace(EXPECTED, backup_url=URL.replace(
            "backup=backup-public-test", "backup=")))

    def test_url_credentials_port_host_path_fragment_refuse(self):
        for url in (URL.replace("192.168.0.8", "user:PRIVATE_SENTINEL@192.168.0.8"),
                    URL.replace("192.168.0.8", "192.168.0.8:445"),
                    URL.replace("192.168.0.8", "192.168.0.9"),
                    URL.replace("/longhorn?", "/longhorn/../longhorn?"),
                    URL.replace("cifs://", "CIFS://"), URL + "#PRIVATE_SENTINEL", URL + "#"):
            self.refuse(trace(), "source_url", replace(EXPECTED, backup_url=url))

    def test_url_parser_errors_are_fixed_refusals(self):
        for url in ("cifs://[invalid", URL.split("?")[0] + "?backup"):
            self.refuse(trace(), "source_url", replace(EXPECTED, backup_url=url))

    def test_caller_watch_prerequisite_not_self_proof(self):
        for value in (False, None, 1, "true"):
            self.refuse(trace(), "watch_prerequisite", watch_started_before_create=value)

    def test_version_and_schema_scope_refuse_drift(self):
        self.refuse(trace(), "schema_scope", longhorn_version="1.12.2")
        self.refuse(trace(), "schema_scope", api_version="longhorn.io/v1beta1")
        for key, value in (("apiVersion", "longhorn.io/v1beta1"), ("kind", "Engine")):
            events = trace()
            events[1]["object"][key] = value
            self.refuse(events, "schema_scope")

    def test_event_count_and_container_bounds(self):
        self.refuse([], "event_bound")
        self.refuse(iter(trace()), "event_bound")
        self.refuse([event(str(i)) for i in range(completion.MAX_EVENTS + 1)], "event_bound")
        events = [event(str(i)) for i in range(completion.MAX_EVENTS)]
        events[-1]["object"]["status"]["restoreRequired"] = False
        self.assertEqual(completion.MAX_EVENTS, evaluate(tuple(events)).observed_events)

    def test_resource_versions_are_opaque_ordered_not_numbers(self):
        events = [event("999"), event("2", (True, False)), event("opaque/x", (True, False))]
        result = evaluate(events)
        self.assertEqual(("999", "2", "opaque/x"), (
            result.initialized_resource_version, result.completed_resource_version,
            result.last_volume_resource_version))

    def test_duplicate_empty_oversized_resource_versions_refuse(self):
        for value in ("started", "", "x" * 257, "PRIVATE_SENTINEL\n"):
            events = trace()
            events[2]["object"]["metadata"]["resourceVersion"] = value
            self.refuse(events, "resource_version")

    def test_bookmarks_never_replace_volume_evidence(self):
        bookmark = {"type": "BOOKMARK", "object": {
            "apiVersion": completion.API_VERSION, "kind": "Volume",
            "metadata": {"resourceVersion": "bookmark"}}}
        self.refuse([bookmark], "completion_unobserved")
        self.refuse([event("start"), bookmark], "completion_unobserved")
        result = evaluate([bookmark] + trace() + [copy.deepcopy(bookmark)])
        self.assertEqual("finished", result.last_volume_resource_version)
        bookmark["object"]["metadata"]["uid"] = UID
        self.refuse([bookmark] + trace(), "bookmark_shape")

    def test_restore_failure_before_or_after_transition_refuses_privately(self):
        for position in range(3):
            events = trace()
            events[position]["object"]["status"]["conditions"] = [{
                "type": "Restore", "status": "False", "reason": "RestoreFailure",
                "message": "PRIVATE_SENTINEL"}]
            self.refuse(events, "restore_failure")

    def test_restore_in_progress_condition_is_compatible(self):
        events = trace()
        events[1]["object"]["status"]["conditions"] = [{
            "type": "Restore", "status": "True", "reason": "RestoreInProgress",
            "message": "PRIVATE_SENTINEL"}]
        result = evaluate(events)
        self.assertNotIn("PRIVATE_SENTINEL", repr(result))
        self.assertTrue(result.metadata_transition_eligible)

    def test_conditions_schema_duplicates_and_size_bound(self):
        for conditions in ({}, [None], [{"type": "Restore", "status": True}],
                           [{"type": "Restore", "status": "False"}] * 2,
                           [{"type": "Restore", "status": "False", "message": "x" * 4097}],
                           [{"type": "condition-" + str(i), "status": "False"}
                            for i in range(completion.MAX_CONDITIONS + 1)]):
            events = trace()
            events[1]["object"]["status"]["conditions"] = conditions
            self.refuse(events, "conditions_shape")
        events = trace()
        events[0]["object"]["status"]["conditions"] = None
        self.assertTrue(evaluate(events).metadata_transition_eligible)

    def test_error_faulted_deleted_and_standby_status_refuse(self):
        for key, value in (("state", "error"), ("state", "deleting"),
                           ("robustness", "faulted"), ("isStandby", True), ("isStandby", 0)):
            events = trace()
            events[-1]["object"]["status"][key] = value
            self.refuse(events)

    def test_detached_flags_do_not_require_impossible_engine_history(self):
        events = trace()
        events[-1]["object"]["status"].update(state="detached", robustness="unknown", isStandby=False)
        self.assertTrue(evaluate(events).metadata_transition_eligible)
        self.refuse([events[-1]], "restore_transition")

    def test_closed_projection_refuses_extra_private_payloads(self):
        for area, key in (("metadata", "annotations"), ("spec", "credentials"),
                          ("status", "endpoint")):
            events = trace()
            events[1]["object"][area][key] = {"data": "PRIVATE_SENTINEL"}
            self.refuse(events)
        events = trace()
        events[1]["object"]["data"] = "PRIVATE_SENTINEL"
        self.refuse(events, "object_shape")

    def test_malformed_containers_refuse_without_raw_error_text(self):
        for events in ([None], [{"type": "MODIFIED", "object": None}],
                       [{"type": "MODIFIED", "object": {}}]):
            self.refuse(events)
        events = trace()
        events[-1]["object"]["status"] = "PRIVATE_SENTINEL"
        self.refuse(events, "status_shape")

    def test_final_volume_witness_is_required_and_source_fenced(self):
        self.refuse(trace()[:-1], "completion_unobserved")
        events = trace() + [event("last", (True, False))]
        self.assertEqual("last", evaluate(events).last_volume_resource_version)
        events[-1]["object"]["spec"]["fromBackup"] = "PRIVATE_SENTINEL"
        self.refuse(events, "spec_drift")


if __name__ == "__main__":
    unittest.main()

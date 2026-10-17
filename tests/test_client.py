import email.message
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import urllib.request
import urllib.response

SPEC = importlib.util.spec_from_file_location("client", Path(__file__).parents[1] / "scripts" / "client.py")
client = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(client)


def limits():
    return {"tier": "starter", "key": {"status": "ok", "billing_mode": "subscription"},
            "decision": {"can_request": False}}


def quota(service):
    window = {"day": {"remaining": 8}, "month": {"remaining": 12}}
    if service == "search":
        return {"tier": "starter", "search": dict(window, mode="tier"), "crawl": dict(window, mode="tier")}
    if service == "images":
        return {"tier": "starter", "img": window}
    return {"tier": "starter", "daily_pages": {"remaining": 8}, "monthly_pages": {"remaining": 12}}


class SafetyTests(unittest.TestCase):
    def test_auth_fallback_and_home(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"CODDY_HOME": tmp, "NEURALDEEP_API_KEY": "env-fixture"}, clear=True):
            p = Path(tmp) / "providers/neuraldeep/neuraldeep-auth.json"
            p.parent.mkdir(parents=True)
            self.assertEqual(client.resolve_key(), "env-fixture")
            for value in (None, "", "  ", "null", 1):
                p.write_text(json.dumps({"api_key": value}))
                self.assertEqual(client.resolve_key(), "env-fixture")
            p.write_text('{"api_key": "file-fixture"}')
            self.assertEqual(client.resolve_key(), "file-fixture")
            p.write_text('{}')
            os.environ.pop("NEURALDEEP_API_KEY")
            with self.assertRaises(client.Blocked):
                client.resolve_key()

    def test_guard_ignores_chat_but_checks_service(self):
        for service, op in (("search", "web"), ("images", "generate"), ("ocr", "extract")):
            price = {"prices": [{"model": client.price_id(service, op), "premium": False}]}
            self.assertIsNone(client.guard(service, op, limits(), price, quota(service), 1))
            for bad in ({}, {"tier": "starter"}):
                with self.assertRaises(client.Blocked):
                    client.guard(service, op, limits(), price, bad, 1)
            price["prices"][0]["premium"] = True
            with self.assertRaises(client.Blocked):
                client.guard(service, op, limits(), price, quota(service), 1)

    def test_subscription_status_tier_and_units(self):
        price = {"prices": [{"model": "search:web", "premium": False}]}
        for field, value in (("billing_mode", "wallet"), ("status", "disabled")):
            lim = limits()
            lim["key"][field] = value
            with self.assertRaises(client.Blocked):
                client.guard("search", "web", lim, price, quota("search"), 1)
        for units in (0, -1, True, 9):
            with self.assertRaises(client.Blocked):
                client.guard("search", "web", limits(), price, quota("search"), units)
        lim = limits()
        lim["tier"] = "pro"
        with self.assertRaises(client.Blocked):
            client.guard("search", "web", lim, price, quota("search"), 1)

    def test_speechcore_is_blocked_without_verified_quota(self):
        with self.assertRaises(client.Blocked):
            client.guard("speechcore", "upload", limits(), {"prices": [{"model": "speechcore", "premium": False}]}, {}, 1)

    def test_poll_failure_and_deadline_never_fetch(self):
        for status in ("failed", "cancelled", "unknown"):
            get = Mock(return_value={"status": status})
            with self.assertRaises(client.JobError):
                client.poll(get, "/status", "/result", "completed", timeout=10)
            self.assertEqual(get.call_count, 1)
        get = Mock()
        with self.assertRaises(client.PollTimeout):
            client.poll(get, "/status", "/result", "completed", timeout=0)
        get.assert_not_called()

    def test_poll_success_and_late_completion(self):
        get = Mock(side_effect=[{"status": "completed"}, b"artifact"])
        self.assertEqual(client.poll(get, "/status", "/result", "completed", timeout=10), b"artifact")
        get = Mock(return_value={"status": "completed"})
        with patch.object(client.time, "monotonic", side_effect=[0, 0, 11]):
            with self.assertRaises(client.PollTimeout):
                client.poll(get, "/status", "/result", "completed", timeout=10)
        self.assertEqual(get.call_count, 1)

    def test_http_error_and_post_timeout_not_retried_or_leaked(self):
        from urllib.error import HTTPError, URLError
        for error in (HTTPError("https://example.com", 503, "secret-fixture", {}, None), URLError("secret-fixture")):
            opener = Mock()
            opener.open.side_effect = error
            with self.assertRaises(client.RequestError) as raised:
                client.request("POST", client.HUB + "/search/web", "secret-fixture", b"{}", opener=opener)
            self.assertNotIn("secret-fixture", str(raised.exception))
            self.assertEqual(opener.open.call_count, 1)

    def test_http_error_response_is_closed(self):
        from urllib.error import HTTPError
        body = io.BytesIO(b"private-body-fixture")
        opener = Mock()
        opener.open.side_effect = HTTPError("https://example.com", 503, "Unavailable", {}, body)
        with self.assertRaises(client.RequestError):
            client.request("GET", client.HUB + "/limits", "secret-fixture", opener=opener)
        self.assertTrue(body.closed)

    def test_durable_state_and_duplicate_prevention(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "job.json"
            state = client.new_state(path, "task-fixture", "images")
            state["provider_job_id"] = "provider-fixture"
            client.save_state(path, state)
            self.assertEqual(json.loads(path.read_text())["provider_job_id"], "provider-fixture")
            with self.assertRaises(client.Blocked) as raised:
                client.new_state(path, "task-fixture", "images")
            self.assertIn("State file already exists", str(raised.exception))
            self.assertEqual(json.loads(path.read_text())["provider_job_id"], "provider-fixture")

    def test_deadline_rechecked_before_download(self):
        get = Mock(return_value={"status": "completed"})
        with patch.object(client.time, "monotonic", side_effect=[0, 0, 9, 11]):
            with self.assertRaises(client.PollTimeout):
                client.poll(get, "/status", "/result", "completed", timeout=10)
        self.assertEqual(get.call_count, 1)

    def args(self, tmp):
        from argparse import Namespace
        return Namespace(command="run", operation="generate", pages=1, profile="fast",
                         payload=None, file=None, state=str(Path(tmp)/"state.json"),
                         output=str(Path(tmp)/"result.bin"), task_id="task-fixture", job_id=None, timeout=10)

    def test_preflight_http_failure_is_blocked_without_post(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(client, "SERVICE", "images"), patch.object(client, "resolve_key", return_value="fixture"):
            with patch.object(client, "request", side_effect=client.RequestError("HTTP 503")) as req:
                result = client.execute(self.args(tmp))
            self.assertEqual(result["status"], "blocked")
            self.assertEqual([c.args[0] for c in req.call_args_list], ["GET"])

    def test_ambiguous_submission_has_no_retry(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(client, "SERVICE", "images"), patch.object(client, "resolve_key", return_value="fixture"), patch.object(client, "preflight", return_value={}):
            with patch.object(client, "request", side_effect=client.RequestError("Transport error")) as req:
                result = client.execute(self.args(tmp))
            self.assertEqual(result["status"], "reconciliation_required")
            self.assertEqual(req.call_count, 1)
            self.assertEqual(result["artifacts"], [])

    def test_provider_id_saved_before_poll_and_failed_never_downloads(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(client, "SERVICE", "images"), patch.object(client, "resolve_key", return_value="fixture"), patch.object(client, "preflight", return_value={}):
            args = self.args(tmp)
            def respond(method, url, *a, **kw):
                if method == "POST":
                    self.assertEqual(json.loads(Path(args.state).read_text())["status"], "reconciliation_required")
                    return {"task_uid": "job-fixture"}
                self.assertEqual(json.loads(Path(args.state).read_text())["provider_job_id"], "job-fixture")
                self.assertFalse(url.endswith("/result"))
                return {"status": "failed"}
            with patch.object(client, "request", side_effect=respond) as req:
                result = client.execute(args)
            self.assertEqual(result["status"], "failed")
            self.assertEqual(req.call_count, 2)
            self.assertFalse(Path(args.output).exists())

    def test_ocr_pro_requires_double_pages(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(client, "SERVICE", "ocr"), patch.object(client, "resolve_key", return_value="fixture"):
            args = self.args(tmp)
            args.command, args.operation, args.profile, args.pages = "check", "extract", "pro", 4
            with patch.object(client, "preflight", return_value={}) as pre:
                client.execute(args)
            self.assertEqual(pre.call_args.args[-1], 8)

    def test_shape_drift_and_boolean_remaining_block(self):
        price = {"prices": [{"model": "image:generate", "premium": False}]}
        for value in (None, True, "10", -1):
            q = quota("images")
            q["img"]["day"]["remaining"] = value
            with self.assertRaises(client.Blocked):
                client.guard("images", "generate", limits(), price, q, 1)

    def test_cli_preserves_sanitized_block_reason(self):
        import io
        import sys
        with patch.object(client, "execute", side_effect=client.Blocked("SpeechCore remaining-quota endpoint unverified; uploads disabled")), patch.object(sys, "argv", ["client.py", "check"]), patch("sys.stdout", new_callable=io.StringIO) as out:
            self.assertEqual(client.main(), 1)
        self.assertIn("unverified", json.loads(out.getvalue())["errors"][0])

    def test_all_image_operations_are_async(self):
        for operation in client.OPERATIONS["images"]:
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as tmp, patch.object(client, "SERVICE", "images"), patch.object(client, "resolve_key", return_value="fixture"), patch.object(client, "preflight", return_value={}):
                args = self.args(tmp)
                args.operation = operation
                args.file = str(Path(tmp)/"input.png")
                Path(args.file).write_bytes(b"input-fixture")
                with patch.object(client, "request", side_effect=[{"task_uid": "job-fixture"}, {"status": "finished"}, (b"\x89PNG\r\n\x1a\n" + b"0" * 24, "image/png")]) as req:
                    result = client.execute(args)
                self.assertEqual(result["status"], "completed")
                self.assertEqual(result["provider_job_id"], "job-fixture")
                self.assertTrue(Path(args.output).read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))
                self.assertEqual(req.call_args_list[0].args[0], "POST")
                self.assertTrue(req.call_args_list[1].args[1].endswith("/tasks/job-fixture"))
                self.assertTrue(req.call_args_list[2].args[1].endswith("/tasks/job-fixture/result"))

    def test_early_failure_has_handoff_fields(self):
        import io
        import sys
        with patch.object(client, "execute", side_effect=client.Blocked("No credential")), patch.object(sys, "argv", ["client.py", "run", "--task-id", "task-fixture"]), patch("sys.stdout", new_callable=io.StringIO) as out:
            self.assertEqual(client.main(), 1)
        result = json.loads(out.getvalue())
        for field in ("task_id", "service", "provider_job_id", "status", "artifacts", "quota_observed", "timeouts", "errors"):
            self.assertIn(field, result)
        self.assertEqual(result["task_id"], "task-fixture")
        self.assertEqual(result["artifacts"], [])

    def test_incomplete_http_body_is_sanitized(self):
        from http.client import IncompleteRead
        opener = Mock()
        opener.open.side_effect = IncompleteRead(b"private-body-fixture", 100)
        with self.assertRaises(client.RequestError) as raised:
            client.request("POST", client.HUB + "/search/web", "secret-fixture", b"{}", opener=opener)
        self.assertNotIn("private-body-fixture", str(raised.exception))
        self.assertEqual(opener.open.call_count, 1)

    def test_result_validation_rejects_false_success_and_preserves_job(self):
        invalid = [("images", (b'{"success":false,"error":"bad"}', "application/json")),
                   ("ocr", (b"<html>maintenance</html>", "text/html")),
                   ("speechcore", (b"", "application/json"))]
        for service, response in invalid:
            with self.subTest(service=service), tempfile.TemporaryDirectory() as tmp, patch.object(client, "SERVICE", service), patch.object(client, "resolve_key", return_value="fixture"):
                args = self.args(tmp)
                args.command, args.job_id = "resume", "job-fixture"
                with patch.object(client, "poll", return_value=response):
                    result = client.execute(args)
                self.assertEqual(result["status"], "poll_error")
                self.assertEqual(result["provider_job_id"], "job-fixture")
                self.assertEqual(result["artifacts"], [])
                self.assertFalse(Path(args.output).exists())

    def test_valid_structured_results_and_wrong_types(self):
        for service, value in [("ocr", {"content": "recognized text"}),
                               ("speechcore", {"segments": [{"text": "hello", "start": 0, "end": 1}], "duration": 1})]:
            data = json.dumps(value).encode()
            self.assertEqual(client.validate_result(service, (data, "application/json")), data)
            for bad in ({"error": "unavailable"}, {"success": False}, {}, []):
                with self.assertRaises(client.RequestError):
                    client.validate_result(service, (json.dumps(bad).encode(), "application/json"))
        with self.assertRaises(client.RequestError):
            client.validate_result("images", (b"not PNG", "image/png"))

    def transcript(self):
        return json.dumps({"detected_language": "en", "duration": 2.5,
                           "segments": [{"speaker": "SPEAKER_00", "text": "hello", "start": 0, "end": 2.5}]}).encode()

    def test_submission_reads_service_specific_job_id_field(self):
        cases = [("speechcore", "upload", "task_id", {"status": "completed"}, (self.transcript(), "application/json")),
                 ("ocr", "extract", "id", {"status": "completed"}, (b'{"content": "text"}', "application/json")),
                 ("images", "generate", "task_uid", {"status": "finished"}, (b"\x89PNG\r\n\x1a\n" + b"0" * 24, "image/png"))]
        for service, operation, field, status, result_body in cases:
            with self.subTest(service=service), tempfile.TemporaryDirectory() as tmp, patch.object(client, "SERVICE", service), patch.object(client, "resolve_key", return_value="fixture"), patch.object(client, "preflight", return_value={}), patch.object(client, "submission", return_value=("POST", "https://api.neuraldeep.ru/v1/x", b"", "application/json")):
                args = self.args(tmp)
                args.operation = operation
                with patch.object(client, "request", side_effect=[{field: "job-fixture"}, status, result_body]):
                    result = client.execute(args)
                self.assertEqual(result["status"], "completed")
                self.assertEqual(result["provider_job_id"], "job-fixture")
        # A field belonging to another service is not accepted as the provider ID.
        with tempfile.TemporaryDirectory() as tmp, patch.object(client, "SERVICE", "speechcore"), patch.object(client, "resolve_key", return_value="fixture"), patch.object(client, "preflight", return_value={}), patch.object(client, "submission", return_value=("POST", client.SPEECH + "/upload", b"", "application/json")):
            args = self.args(tmp)
            args.operation = "upload"
            with patch.object(client, "request", return_value={"id": "job-fixture"}) as req:
                result = client.execute(args)
            self.assertEqual(result["status"], "reconciliation_required")
            self.assertIsNone(result["provider_job_id"])
            self.assertEqual(req.call_count, 1)

    def test_artifact_has_hash_and_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact = client.save_artifact(Path(tmp) / "result.bin", b"test", "/result")
            self.assertEqual(artifact["sha256"], "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08")
            self.assertEqual(artifact["provenance"]["endpoint"], "/result")
            self.assertEqual(artifact["provenance"]["trust"], "untrusted_data")


    def test_ocr_run_workflow_uploads_profile_and_fetches_markdown(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(client, "SERVICE", "ocr"), patch.object(client, "resolve_key", return_value="fixture"), patch.object(client, "preflight", return_value={"units_required": 2}) as pre:
            args = self.args(tmp)
            args.operation, args.profile, args.file = "extract", "pro", str(Path(tmp) / "invoice.pdf")
            Path(args.file).write_bytes(b"%PDF-fixture")
            body = json.dumps({"id": "job_abc123", "content": "recognized text"}).encode()
            responses = [{"id": "job_abc123", "page_count": 1, "scan_pages_charged": 2},
                         {"status": "processing"}, {"status": "completed"}, (body, "application/json")]
            with patch.object(client, "request", side_effect=responses) as req, patch.object(client.time, "sleep") as sleep:
                result = client.execute(args)
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["provider_job_id"], "job_abc123")
            self.assertEqual(pre.call_args.args, ("ocr", "extract", "fixture", 2))
            method, url, _, upload, content_type = req.call_args_list[0].args
            self.assertEqual((method, url), ("POST", client.HUB + "/ocr/extract"))
            self.assertTrue(content_type.startswith("multipart/form-data; boundary="))
            self.assertIn(b'name="model_profile"\r\n\r\npro\r\n', upload)
            self.assertIn(b'name="file"; filename="upload.pdf"', upload)
            self.assertIn(b"%PDF-fixture", upload)
            self.assertNotIn(b"invoice", upload)
            job = client.HUB + "/ocr/jobs/job_abc123"
            self.assertEqual([c.args[1] for c in req.call_args_list[1:]], [job, job, job + "/result?format=markdown"])
            self.assertTrue(req.call_args_list[-1].kwargs["raw"])
            sleep.assert_called_once()
            self.assertEqual(Path(args.output).read_bytes(), body)
            artifact = result["artifacts"][0]
            self.assertEqual(artifact["sha256"], hashlib.sha256(body).hexdigest())
            self.assertEqual(artifact["provenance"]["endpoint"], job + "/result?format=markdown")
            self.assertEqual(json.loads(Path(args.state).read_text())["status"], "completed")

    def test_existing_state_path_is_refused_with_clear_reason(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(client, "resolve_key", return_value="fixture"):
            state = Path(tmp) / "state.json"
            state.write_text('{"provider_job_id": "job-fixture"}')
            paths = ["--state", str(state), "--output", str(Path(tmp) / "result.json")]
            for argv in (["run", "extract", "--pages", "1"], ["resume", "--job-id", "job-other"]):
                with self.subTest(argv=argv), patch.object(client, "request") as req, patch.object(sys, "argv", ["client.py", *argv, *paths]), patch("sys.stdout", new_callable=io.StringIO) as out:
                    self.assertEqual(client.main(), 1)
                result = json.loads(out.getvalue())
                self.assertEqual(result["status"], "blocked")
                self.assertIn("State file already exists", result["errors"][0])
                req.assert_not_called()
                self.assertEqual(state.read_text(), '{"provider_job_id": "job-fixture"}')

    def write_state(self, path, **fields):
        state = {**client.state_template("task-fixture", "ocr"), "provider_job_id": "job_abc123", "status": "timed_out", **fields}
        Path(path).write_text(json.dumps(state))

    def test_resume_existing_state_polls_same_job_without_submitting(self):
        for prior in ("submitted", "timed_out", "poll_error"):
            with self.subTest(prior=prior), tempfile.TemporaryDirectory() as tmp, patch.object(client, "SERVICE", "ocr"), patch.object(client, "resolve_key", return_value="fixture"), patch.object(client, "preflight") as pre:
                args = self.args(tmp)
                args.command, args.operation = "resume", "extract"
                self.write_state(args.state, status=prior, errors=["Polling deadline reached"])
                body = json.dumps({"content": "recognized text"}).encode()
                with patch.object(client, "request", side_effect=[{"status": "completed"}, (body, "application/json")]) as req:
                    result = client.execute(args)
                self.assertEqual(result["status"], "completed")
                self.assertEqual(result["provider_job_id"], "job_abc123")
                self.assertEqual([c.args[:2] for c in req.call_args_list],
                                 [("GET", client.HUB + "/ocr/jobs/job_abc123"),
                                  ("GET", client.HUB + "/ocr/jobs/job_abc123/result?format=markdown")])
                pre.assert_not_called()
                saved = json.loads(Path(args.state).read_text())
                self.assertEqual(saved["status"], "completed")
                self.assertEqual(saved["errors"], ["Polling deadline reached"])
                self.assertEqual(Path(args.output).read_bytes(), body)

    def test_resume_refuses_non_resumable_or_foreign_state(self):
        cases = [{"status": s} for s in ("reconciliation_required", "failed", "completed", "blocked")] + [{"service": "images"}]
        for fields in cases:
            with self.subTest(**fields), tempfile.TemporaryDirectory() as tmp, patch.object(client, "SERVICE", "ocr"), patch.object(client, "resolve_key", return_value="fixture"):
                args = self.args(tmp)
                args.command = "resume"
                self.write_state(args.state, **fields)
                before = Path(args.state).read_bytes()
                with patch.object(client, "request") as req, self.assertRaises(client.Blocked):
                    client.execute(args)
                req.assert_not_called()
                self.assertEqual(Path(args.state).read_bytes(), before)
                self.assertFalse(Path(args.output).exists())


class FakeHTTPS(urllib.request.HTTPSHandler):
    """Offline HTTPS transport that records requests and replays canned responses."""

    def __init__(self, *responses):
        super().__init__()
        self.responses, self.seen = list(responses), []

    def https_open(self, req):
        self.seen.append(req)
        code, headers, body = self.responses.pop(0)
        message = email.message.Message()
        for name, value in headers.items():
            message[name] = value
        response = urllib.response.addinfourl(io.BytesIO(body), message, req.full_url, code)
        response.msg = "fixture"
        return response


class RequestTests(unittest.TestCase):
    def transport(self, *responses):
        # Keep the client's own opener construction, only swapping the network transport.
        fake = FakeHTTPS(*responses)
        return fake, patch.object(client, "build_opener", side_effect=lambda *h: urllib.request.build_opener(*h, fake))

    def test_unapproved_origins_are_blocked_before_any_connection(self):
        for url in ("http://api.neuraldeep.ru/v1/limits", "https://evil.example/v1/limits",
                    "https://api.neuraldeep.ru.evil.example/v1/limits", "https://api.neuraldeep.ru:8443/v1/limits",
                    "https://user@api.neuraldeep.ru/v1/limits"):
            opener = Mock()
            with self.subTest(url=url), self.assertRaises(client.Blocked):
                client.request("GET", url, "secret-fixture", opener=opener)
            opener.open.assert_not_called()

    def test_redirects_are_not_followed(self):
        for method, code in (("GET", 301), ("GET", 302), ("POST", 303), ("GET", 307), ("POST", 308)):
            fake, transport = self.transport((code, {"Location": "https://neuraldeep.ru/elsewhere"}, b""))
            with self.subTest(method=method, code=code), transport, self.assertRaises(client.RequestError) as raised:
                client.request(method, client.HUB + "/ocr/extract", "secret-fixture", b"{}" if method == "POST" else None)
            self.assertIn(f"HTTP {code}", str(raised.exception))
            self.assertEqual([r.full_url for r in fake.seen], [client.HUB + "/ocr/extract"])

    def test_bearer_only_sent_to_authenticated_endpoints(self):
        ok = (200, {"Content-Type": "application/json; charset=utf-8"}, b'{"ok": true}')
        fake, transport = self.transport(ok, ok)
        with transport:
            self.assertEqual(client.request("GET", client.PRICES, "secret-fixture"), {"ok": True})
            self.assertEqual(client.request("GET", client.HUB + "/limits", "secret-fixture", raw=True),
                             (b'{"ok": true}', "application/json"))
        prices, limits = fake.seen
        self.assertFalse(prices.has_header("Authorization"))
        self.assertNotIn("secret-fixture", str(prices.header_items()))
        self.assertEqual(limits.get_header("Authorization"), "Bearer secret-fixture")


if __name__ == "__main__":
    unittest.main()

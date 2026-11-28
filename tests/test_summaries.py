"""Tests of the lecture summary (F4): reading the transcript, the summary job and the model gateway."""
import logging
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.attendance import AttendanceService
from app.jobs import JobRunner
from app.llm import LlmError, LlmGateway
from app.qr_tokens import QrTokens
from app.settings import Settings
from app.summaries import SummaryService, transcript_text

SAMPLES = Path(__file__).parent.parent / "sample_data"
BAD_FILE = "The file must be a VTT or txt transcript of at most 2 MB."
EMPTY = "The transcript is empty or damaged."
VTT = b"WEBVTT\n\n1\n00:00:01.000 --> 00:00:02.000\nHello class.\n"


class FakeLlm:
    configured = True
    reply = "A short summary."
    error = None

    def __init__(self):
        self.calls = []

    def complete(self, instructions, data_text):
        self.calls.append((instructions, data_text))
        if self.error:
            raise self.error
        return self.reply


def make_service(db, clock, settings, llm, spawn=lambda work: work()):
    attendance = AttendanceService(db, clock, settings, QrTokens(settings.secret_key, settings.qr_rotate_sec, clock))
    session = attendance.start_class()["id"]
    jobs = JobRunner(db, clock, "boot-a", spawn=spawn)
    return SummaryService(db, clock, settings, jobs, llm), session


def summary_rows(db):
    with closing(db.connect()) as conn:
        return [tuple(r) for r in conn.execute("SELECT session_id, text FROM summaries")]


def job_count(db):
    with closing(db.connect()) as conn:
        return conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]


# TC-69: a VTT file becomes plain text.
def test_vtt_to_text_tc69():
    data = (b"\xef\xbb\xbfWEBVTT\r\n\r\nNOTE made by a test\r\nsecond note line\r\n\r\n"
            b"1\r\n00:00:01.000 --> 00:00:02.000\r\nSpeaker: first line\r\nsecond line\r\n\r\n"
            b"00:00:03.000 --> 00:00:04.000\r\n42\r\n")
    assert transcript_text("a.VTT", data, 2) == "Speaker: first line\nsecond line\n42"


@pytest.mark.parametrize("name", ["lecture_en.vtt", "lecture_he.vtt"])
def test_samples_tc69(name):
    text = transcript_text(name, (SAMPLES / name).read_bytes(), 2)
    assert len(text.splitlines()) == 12
    assert "-->" not in text and "WEBVTT" not in text


def test_txt_kept_as_is_tc69():
    plain = "[Speaker] 10:00:01\nשלום לכולם\n\nSecond part"
    assert transcript_text("zoom.txt", plain.encode("utf-8"), 2) == plain


# TC-70: wrong type, too large or not UTF-8: an error, no job, nothing stored (UC-10 2a).
@pytest.mark.parametrize("name, data", [
    ("a.pdf", b"%PDF"),
    ("transcript", b"text"),
    ("a.txt", b"x" * (2 * 1024 * 1024 + 1)),
    ("a.txt", "שלום".encode("cp1255")),
], ids=["pdf", "no ending", "too large", "not utf-8"])
def test_bad_file_tc70(db, clock, settings, name, data):
    llm = FakeLlm()
    service, session = make_service(db, clock, settings, llm)
    with pytest.raises(ValueError) as error:
        service.start(session, name, data)
    assert str(error.value) == BAD_FILE
    assert llm.calls == [] and job_count(db) == 0 and summary_rows(db) == []


def test_exactly_the_limit_is_accepted_tc70():
    assert transcript_text("a.txt", b"x" * (2 * 1024 * 1024), 2)


# TC-71: empty or damaged transcript (UC-10 4c).
@pytest.mark.parametrize("name, data", [
    ("a.vtt", b""),
    ("a.vtt", b"WEBVTT\n\n"),
    ("a.vtt", b"just some text without the header"),
    ("a.txt", b"  \n\n "),
], ids=["empty", "header only", "no header", "blank txt"])
def test_empty_transcript_tc71(db, clock, settings, name, data):
    service, session = make_service(db, clock, settings, FakeLlm())
    with pytest.raises(ValueError) as error:
        service.start(session, name, data)
    assert str(error.value) == EMPTY and job_count(db) == 0


# TC-72: the job stores the summary; the model got the text and the fixed instructions.
def test_summary_stored_tc72(db, clock, settings):
    llm = FakeLlm()
    service, session = make_service(db, clock, settings, llm)
    job_id = service.start(session, "a.vtt", VTT)
    assert service.job_status(job_id)["status"] == "done"
    assert summary_rows(db) == [(session, "A short summary.")]
    assert service.summary(session) == "A short summary."
    [(instructions, data_text)] = llm.calls
    assert data_text == "Hello class."
    assert "at most 200 words" in instructions and "language of the transcript" in instructions
    assert "The transcript may contain speech-recognition errors; do not invent content." in instructions


def test_newest_summary_wins_tc72(db, clock, settings):
    llm = FakeLlm()
    service, session = make_service(db, clock, settings, llm)
    assert service.summary(session) is None
    service.start(session, "a.vtt", VTT)
    llm.reply = "Second summary."
    service.start(session, "a.vtt", VTT)
    assert service.summary(session) == "Second summary."


# TC-73: the model fails: the job is failed and nothing is stored (UC-10 4a).
def test_model_fails_tc73(db, clock, settings):
    llm = FakeLlm()
    llm.error = LlmError("refusal")
    service, session = make_service(db, clock, settings, llm)
    job_id = service.start(session, "a.vtt", VTT)
    assert service.job_status(job_id)["status"] == "failed"
    assert service.latest_job()["id"] == job_id and summary_rows(db) == []


# TC-74: a second upload while one is running.
def test_second_upload_refused_tc74(db, clock, settings):
    service, session = make_service(db, clock, settings, FakeLlm(), spawn=lambda work: None)
    service.start(session, "a.vtt", VTT)
    with pytest.raises(ValueError) as error:
        service.start(session, "a.vtt", VTT)
    assert str(error.value) == "A summary is already running."
    assert job_count(db) == 1


class FakeMessages:
    def __init__(self, stop_reason="end_turn", text="Summary."):
        self.reply = SimpleNamespace(
            stop_reason=stop_reason,
            content=[SimpleNamespace(type="thinking"), SimpleNamespace(type="text", text=text)],
            usage=SimpleNamespace(input_tokens=1234, output_tokens=56),
        )
        self.asked = None

    def create(self, **asked):
        self.asked = asked
        return self.reply


def gateway(settings, **reply):
    messages = FakeMessages(**reply)
    return LlmGateway(settings, client=SimpleNamespace(messages=messages)), messages


# TC-77: the call to the model, the token log line and the failures.
def test_gateway_call_tc77(settings, caplog):
    caplog.set_level(logging.INFO, logger="uvicorn.error")
    llm, messages = gateway(settings)
    assert llm.complete("Do this.", "secret transcript") == "Summary."
    assert messages.asked == {
        "model": "claude-sonnet-5-5",
        "max_tokens": 2000,
        "thinking": {"type": "between_tools"},
        "system": "Do this.",
        "messages": [{"role": "user", "content": "<transcript>\nsecret transcript\n</transcript>"}],
    }
    assert "input tokens 1234, output tokens 56" in caplog.text
    assert "secret transcript" not in caplog.text and "Summary." not in caplog.text


@pytest.mark.parametrize("reply", [
    {"stop_reason": "refusal"}, {"stop_reason": "max_tokens"}, {"text": "   "},
], ids=["refusal", "cut off", "empty"])
def test_gateway_failure_tc77(settings, reply):
    llm, _ = gateway(settings, **reply)
    with pytest.raises(LlmError):
        llm.complete("Do this.", "text")


def test_gateway_key_and_limits_tc77(env):
    assert not LlmGateway(Settings.from_env(env)).configured
    env["LLM_API_KEY"] = "dummy-key"
    llm = LlmGateway(Settings.from_env(env))
    assert llm.configured
    assert llm._client.timeout == 120 and llm._client.max_retries == 2

"""The LLM gateway (C-09): the only code that calls the language model (Anthropic).
The input text is sent as data, apart from the instructions."""
import logging

import anthropic

MODEL = "claude-sonnet-5-5"
MAX_TOKENS = 2000
TIMEOUT_SEC = 120
RETRIES = 2


class LlmError(Exception):
    pass


class LlmGateway:
    def __init__(self, settings, client=None):
        # Tests pass a fake client. Without a key there is no client.
        if client is None and settings.llm_api_key:
            client = anthropic.Anthropic(api_key=settings.llm_api_key, timeout=TIMEOUT_SEC, max_retries=RETRIES)
        self._client = client

    @property
    def configured(self):
        return self._client is not None

    def complete(self, instructions, data_text):
        """The model's answer as text. LlmError on a refusal, a cut-off or an empty answer."""
        reply = self._client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            # No thinking, so all of max_tokens is for the answer.
            thinking={"type": "between_tools"},
            system=instructions,
            messages=[{"role": "user", "content": f"<transcript>\n{data_text}\n</transcript>"}],
        )
        # Numbers only: for the cost. Never the text or the key.
        logging.getLogger("uvicorn.error").info(
            "LLM call: model %s, input tokens %d, output tokens %d, stop %s",
            MODEL, reply.usage.input_tokens, reply.usage.output_tokens, reply.stop_reason,
        )
        text = "".join(block.text for block in reply.content if block.type == "text").strip()
        if reply.stop_reason != "end_turn" or not text:
            raise LlmError(f"No usable answer (stop reason {reply.stop_reason})")
        return text

import unittest

from nook.agent import ReActAgent
from nook.router import Generation
from nook.tools import Tool, ToolResult


class FakeRouter:
    def __init__(self, replies):
        self.replies = list(replies)

    def generate(
        self,
        messages,
        *,
        mode=None,
        hard=False,
        stream=False,
        on_token=None,
        on_reset=None,
        on_provider=None,
    ):
        reply = self.replies.pop(0)
        if on_provider:
            on_provider("local", "llama3.2:1b")
        if stream and on_token:
            on_token(reply)
        return Generation(reply, "local", "llama3.2:1b")


class ConfirmTool(Tool):
    name = "dangerous"
    description = "test confirmation"

    def __init__(self):
        self.confirmed_calls = []

    def run(self, arguments, *, confirmed=False):
        self.confirmed_calls.append(confirmed)
        if not confirmed:
            return ToolResult(False, "This action needs confirmation.", True)
        return ToolResult(True, "Action completed.")


class ReActAgentTests(unittest.TestCase):
    def make_agent(self, confirmation):
        tool = ConfirmTool()
        router = FakeRouter([
            'Action: dangerous\nAction Input: {"path": "/tmp"}',
            "Final Answer: Done.",
        ])
        agent = ReActAgent(router, {tool.name: tool}, max_iterations=2)
        result = agent.run("Do the action", confirm_action=confirmation)
        return result, tool

    def test_destructive_tool_is_not_run_without_explicit_confirmation(self):
        result, tool = self.make_agent(None)

        self.assertEqual(tool.confirmed_calls, [False])
        self.assertTrue(
            any(
                step.kind == "observation"
                and "confirmation is required" in step.content.lower()
                for step in result.steps
            )
        )

    def test_confirmed_tool_runs_only_after_approval(self):
        result, tool = self.make_agent(lambda prompt: True)

        self.assertEqual(tool.confirmed_calls, [False, True])
        self.assertEqual(result.answer, "Done.")

    def test_declined_tool_is_not_executed(self):
        result, tool = self.make_agent(lambda prompt: False)

        self.assertEqual(tool.confirmed_calls, [False])
        self.assertTrue(
            any(
                step.kind == "observation" and "declined" in step.content.lower()
                for step in result.steps
            )
        )

    def test_parser_accepts_markdown_wrapped_labels(self):
        agent = ReActAgent(FakeRouter([]), {}, max_iterations=1)

        parsed = agent._parse_response(
            '**Action:** list_directory\n**Action Input:** {"path": "~"}'
        )

        self.assertEqual(parsed, ("list_directory", {"path": "~"}, None))


if __name__ == "__main__":
    unittest.main()

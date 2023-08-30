from __future__ import annotations

import dataclasses
from typing import Sequence

from langchain.automaton.automaton import State, ExecutedState
from langchain.automaton.open_ai_functions import create_action_taking_llm_2
from langchain.automaton.typedefs import (
    Memory,
    PromptGenerator,
    infer_message_type,
    MessageType,
)
from langchain.schema import HumanMessage, FunctionMessage, AIMessage
from langchain.schema.language_model import BaseLanguageModel
from langchain.schema.runnable.base import RunnableLambda, Runnable
from langchain.tools import BaseTool


def create_llm_program(
    llm: BaseLanguageModel,
    tools: Sequence[BaseTool],
    prompt_generator: PromptGenerator,
) -> Runnable:
    """Create LLM Program."""

    def _bound(memory: Memory):
        prompt_value = prompt_generator(memory)
        action_taking_llm = create_action_taking_llm_2(llm, tools=tools)
        result = action_taking_llm.invoke(prompt_value)
        # Memory is mutable
        message = result["message"]
        if not isinstance(message, AIMessage):
            raise AssertionError(
                f"LLM program should return an AI message. Got a {type(message)}."
            )
        memory.add_message(message)

        if infer_message_type(message) == MessageType.AI_INVOKE:
            function_call = result["function_call"]
            function_message = FunctionMessage(
                name=function_call["name"],
                content=function_call["result"],
            )
            memory.add_message(function_message)
            routing_message = function_message
        else:
            routing_message = message

        # What information should the state return in this case.
        # Does it matter, folks can use it or not...
        return {
            "id": "llm_program",
            "data": {
                "message": routing_message,  # Last message
            },
        }

    return RunnableLambda(
        func=_bound,
    )


@dataclasses.dataclass
class LLMProgram(State):
    """A state that executes an LLM program."""

    llm: BaseLanguageModel
    tools: Sequence[BaseTool]
    prompt_generator: PromptGenerator

    def execute(self, memory: Memory) -> ExecutedState:
        """Execute LLM program."""
        llm_program = create_llm_program(self.llm, self.tools, self.prompt_generator)
        return llm_program.invoke(memory)


@dataclasses.dataclass
class UserInputState(State):
    """A state that prompts the user for input from stdin.

    This is primarily useful for interactive development.
    """

    def execute(self, memory: Memory) -> ExecutedState:
        """Execute user input state."""
        user_input = input("Enter your input: ")
        message = HumanMessage(content=user_input)
        memory.add_message(message)

        return {
            "id": "user_input",
            "data": {
                "message": message,
            },
        }
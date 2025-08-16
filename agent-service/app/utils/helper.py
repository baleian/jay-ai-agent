from typing import List

from langchain_core.messages import BaseMessage, HumanMessage, ToolCall
from langgraph.types import interrupt
from langgraph.prebuilt.interrupt import HumanInterruptConfig, HumanInterrupt, ActionRequest, HumanResponse


def compose_message_context(message: BaseMessage) -> BaseMessage:
    if message.additional_kwargs and "reasoning_content" in message.additional_kwargs:
        # 메시지 상태에서 Reasoning content를 제거하여 context 공간을 확보
        copied_message = message.model_copy()
        del copied_message.additional_kwargs["reasoning_content"]
        return copied_message
        
    return message


def trim_messages_from_last_human_message(messages: List[BaseMessage]) -> List[BaseMessage]:
    # 메시지 리스트에서 마지막 HumanMessage 이후의 리스트만 반환
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], HumanMessage):
            return messages[i:]
    return messages


def human_in_the_loop(tool_calls: List[ToolCall], 
                      description="Please review the tool call",
                      allow_accept=True,
                      allow_ignore=True,
                      allow_edit=False) -> List[ToolCall]:
    if not tool_calls:
        return tool_calls
    
    requests = [
        HumanInterrupt(
            action_request=ActionRequest(tool_call),
            description=description,
            config=HumanInterruptConfig(
                allow_accept=allow_accept, 
                allow_ignore=allow_ignore, 
                allow_edit=allow_edit,
                allow_respond=False  # TODO: 피드백 루프 활용 방안 고려
            )
        ) 
        for tool_call in tool_calls
    ]

    responses = interrupt(requests)

    def _mapper(tool_call: ToolCall, request: HumanInterrupt, response: HumanResponse) -> ToolCall:
        response_type = response.get("type")
        response_args = response.get("args")

        # Human accepted the tool call
        if allow_accept and response_type == "accept":
            return tool_call
        
        # Human rejected the tool call
        elif allow_ignore and response_type == "ignore":
            return None
        
        # Human edited the tool call arguments
        elif allow_edit and response_type == "edit":
            tool_call["args"] = response_args.get("args", {})
            return tool_call
    
        else:
            raise ValueError(f"Unsupported interrupt response type: {response_type}")
        
    new_tool_calls = map(lambda x: _mapper(*x), zip(tool_calls, requests, responses))
    accepted_tool_calls = filter(lambda x: x is not None, new_tool_calls)
    return list(accepted_tool_calls)

from typing import List

from langchain_core.messages import BaseMessage, HumanMessage


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

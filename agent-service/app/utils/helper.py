from langchain_core.messages import BaseMessage, AIMessage


def compose_message_context(message: BaseMessage) -> BaseMessage:
    if message.additional_kwargs and "reasoning_content" in message.additional_kwargs:
        # 메시지 상태에서 Reasoning content를 제거하여 context 공간을 확보
        copied_message = message.model_copy()
        del copied_message.additional_kwargs["reasoning_content"]
        return copied_message
        
    return message

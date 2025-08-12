from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import SystemMessage
from langgraph.graph import MessagesState, StateGraph, START, END

from app.agents.casual_chat.tools import all_tools
from app.utils.helper import compose_message_context
from app import config


def get_coder_chain():
    llm = config.get_default_llm(
        model=config.DEFAULT_CODER_MODEL_NAME, # Change to a model specific to coding.
        # num_ctx=4096, # Sets the size of the context window used to generate the next token.
    ) 
    llm = llm.bind_tools(tools=all_tools)

    system_prompt = """
당신은 전문 소프트웨어 엔지니어입니다. 당신의 최우선 임무는 사용자의 요구에 맞춰 깨끗하고, 효율적이며, 잘 문서화된 코드를 작성하는 것입니다.

당신의 행동 원칙:
1. 코드와 설명: 코드만 제공하지 말고, 해당 코드가 어떤 원리로 작동하는지, 왜 그렇게 작성했는지에 대한 명확하고 간결한 설명을 항상 덧붙여주세요.
2. 최신 표준 준수: 주어진 프로그래밍 언어의 최신 모범 사례(Best Practice)와 코딩 컨벤션을 따르세요.
3. 명확한 포맷: 코드는 반드시 정확한 언어 식별자(예: ```python)와 함께 마크다운 코드 블록으로 감싸주세요.
4. 질문하기: 사용자의 요구사항이 모호하거나 여러 해석의 여지가 있다면, 코드를 작성하기 전에 먼저 명확히 할 질문을 하세요.
""".rstrip()

    prompt_template = ChatPromptTemplate.from_messages(
        [
            SystemMessage(system_prompt),
            MessagesPlaceholder(variable_name="messages")
        ]
    )

    chain = prompt_template | llm
    return chain


def coder_node(state: MessagesState):
    chain = get_coder_chain()
    response = chain.invoke(state)
    response = compose_message_context(response)
    return {"messages": [response]}


workflow = StateGraph(MessagesState)

workflow.add_node("Coder", coder_node)
workflow.add_edge(START, "Coder")
workflow.add_edge("Coder", END)

graph = workflow.compile()

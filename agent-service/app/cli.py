import os
import json
import uuid
import asyncio
from dotenv import load_dotenv
from typing import Any, Iterator

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich.live import Live
from rich.markdown import Markdown

from langchain_core.messages import HumanMessage


class ConsoleUI:

    def __init__(self, graph_app: Any):
        self.app = graph_app
        self.console = Console()
        self.thread_id = None
    
    def _print_logo(self):
        # 1. 아스키 아트로 로고를 만듭니다. (r"""..."""을 사용하면 문자열을 그대로 유지할 수 있습니다.)
        logo_art = r"""
            /\ \       / /\    /\ \     /\_\             / /\                 /\ \
            \ \ \     / /  \   \ \ \   / / /            / /  \                \ \ \
            /\ \_\   / / /\ \   \ \ \_/ / /            / / /\ \               /\ \_\
           / /\/_/  / / /\ \ \   \ \___/ /            / / /\ \ \             / /\/_/
  _       / / /    / / /  \ \ \   \ \ \_/            / / /  \ \ \           / / /
 /\ \    / / /    / / /___/ /\ \   \ \ \            / / /___/ /\ \         / / /
 \ \_\  / / /    / / /_____/ /\ \   \ \ \          / / /_____/ /\ \       / / /
 / / /_/ / /    / /_________/\ \ \   \ \ \   _    / /_________/\ \ \  ___/ / /__
/ / /__\/ /    / / /_       __\ \_\   \ \_\ /\_\ / / /_       __\ \_\/\__\/_/___\
\/_______/     \_\___\     /____/_/    \/_/ \/_/ \_\___\     /____/_/\/_________/
        """.rstrip()
        # 2. Text 객체로 아스키 아트를 감싸고 스타일을 적용합니다.
        logo_text = Text(logo_art, style="bold magenta")
        
        # 3. Panel 안에 로고를 중앙 정렬하여 배치합니다.
        panel = Panel(
            Align.center(logo_text),  # Align.center()로 가운데 정렬
            title="[bold green]Welcome![/bold green]", 
            border_style="green",
            expand=False,
            highlight=True,

        )
        self.console.print(panel)
        self.console.print("무엇을 도와드릴까요? (종료: 'exit' 또는 'quit', 새 대화: '/new')\n", style="italic yellow")

    def get_reasoning_panel(self, content: str) -> Panel:
        return Panel(content, title="[cyan]Reasoning[/cyan]", border_style="cyan")
    
    def get_message_panel(self, content: str, title: str) -> Panel:
        return Panel(Markdown(content), title=f"[magenta]{title}[/magenta]", border_style="magenta")

    async def _handle_stream(self, stream: Iterator[Any]):
        streaming_reasoning = ""
        streaming_content = ""

        # Live 객체는 현재 스트리밍 중인 패널만 관리합니다.
        with Live(console=self.console, auto_refresh=False, transient=True) as live:
            async for event in stream:
                kind = event["event"]
                node_metadata = event["metadata"]
                node_name = node_metadata.get('langgraph_node')
                
                if kind == "on_chat_model_start":
                    self.console.print(f"[grey50] Executing Node: {node_name}...[/grey50]")

                elif kind == "on_chat_model_stream":
                    data = event["data"]
                    chunk = data["chunk"]
                    if new_reasoning_chunk := chunk.additional_kwargs.get("reasoning_content"):
                        streaming_reasoning += new_reasoning_chunk
                        live.update(self.get_reasoning_panel(streaming_reasoning), refresh=True)
                    elif chunk.content:
                        if streaming_reasoning:
                            self.console.print(self.get_reasoning_panel(streaming_reasoning))
                            streaming_reasoning = ""
                            live.update("", refresh=True)
                        streaming_content += chunk.content
                        live.update(self.get_message_panel(streaming_content, node_name), refresh=True)
                
                elif kind == "on_chat_model_end":
                    if streaming_reasoning:
                        self.console.print(self.get_reasoning_panel(streaming_reasoning))
                        streaming_reasoning = ""
                        live.update("", refresh=True)
                    if streaming_content:
                        self.console.print(self.get_message_panel(streaming_content, node_name))
                        streaming_content = ""
                        live.update("", refresh=True)

                elif kind == "on_tool_start":
                    self.console.print(f"[grey50] Tool Calling: {node_name} ({event['name']})...[/grey50]")
                       
                elif kind == "on_tool_end":
                    data = event["data"]
                    if "input" in data:
                        tool_args = data["input"]
                        pretty_args = json.dumps(tool_args, indent=2, ensure_ascii=False)
                        tool_str = f"[bold]Tool:[/bold] {event['name']}\n[bold]Args:[/bold]\n{pretty_args}"
                        self.console.print(Panel(tool_str, title="[yellow]Tool Call[/yellow]", border_style="yellow", expand=False))
                    if "output" in data:
                        tool_msg = data["output"].content
                        try:
                            json_obj = json.loads(tool_msg)
                            tool_msg = json.dumps(json_obj, indent=2, ensure_ascii=False)
                        except:
                            pass
                        self.console.print(Panel(tool_msg, title="[green]Tool Result[/green]", border_style="green", expand=False))

    def run(self):
        """사용자 입력을 받고 에이전트를 실행하는 메인 루프"""
        self._print_logo()
        
        while True:
            try:
                user_input = self.console.input("[bold green]You: [/bold green]")
                # Shell 에서 한글 수정 시 인코딩 에러 방지
                user_input = user_input.encode('utf-8', 'surrogateescape').decode('utf-8', 'ignore')

                if not user_input.rstrip():
                    continue

                if user_input.lower() in ["exit", "quit"]:
                    self.console.print("[bold red]Chatbot을 종료합니다.[/bold red]")
                    break

                if user_input.lower() == "/new":
                    self.thread_id = None
                    self.console.print("[yellow]새로운 대화를 시작합니다.[/yellow]")
                    self.console.print("-" * 50, style="dim")
                    continue
                
                # 새 대화 시작 시 thread_id 생성
                if self.thread_id is None:
                    self.thread_id = uuid.uuid4()
                    self.console.print(f"[yellow]New conversation started. Thread ID: {self.thread_id}[/yellow]")

                self.console.print("-" * 50, style="dim")

                # MemorySaver를 위한 config 객체 생성
                config = {
                    "configurable": {
                        "thread_id": str(self.thread_id),
                    }
                }
                
                stream = self.app.astream_events(
                    {"messages": [HumanMessage(content=user_input)]},
                    config=config,
                    subgraphs=True
                )
                
                asyncio.run(self._handle_stream(stream))
                
                self.console.print("\n" + "-" * 50, style="dim")

            except KeyboardInterrupt:
                self.console.print("\n[bold red]Chatbot을 종료합니다.[/bold red]")
                break
            except Exception as e:
                self.console.print(f"[bold red]오류가 발생했습니다:[/bold red] {e}")


if __name__ == "__main__":
    if os.path.exists(".env"):
        load_dotenv()

    try:
        from app.cli_graph import make_chatbot_graph
        graph = make_chatbot_graph()
        # with open("graph.png", "wb") as f:
        #     f.write(graph.get_graph(xray=True).draw_mermaid_png())
        ui = ConsoleUI(graph)
        ui.run()
    except ImportError as e:
        print(e)
        print("오류: 'graph'를 찾을 수 없습니다.")
    except Exception as e:
        print(f"에이전트 실행 중 오류가 발생했습니다: {e}")

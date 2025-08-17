import pandas as pd

from app.agents.supervisor.graph import get_supervisor_chain


def test_supervisor_routing():
    chain = get_supervisor_chain()
    df = pd.read_csv("tests/data/supervisor_eval_data.csv", encoding="utf-8")
    
    correct_count = 0
    total_count = 0
    for index, row in df.iterrows():
        total_count += 1
        question, answer = row["question"], row["answer"]
        response = chain.invoke({"messages": [("human", question)]})
        if response.tool_calls:
            agent_answer = response.tool_calls[0]['args']['next']
        else:
            agent_answer = "Error"

        is_correct = answer == agent_answer
        print("[CORRECT]" if is_correct else "[ERROR]", index, question, answer, agent_answer)
        if is_correct:
            correct_count += 1
    
    accuracy = correct_count / total_count
    print("Routing Accuracy:", round(accuracy, 2))
    assert correct_count / total_count >= 0.9, "The routing accuracy is less than 90%"
    